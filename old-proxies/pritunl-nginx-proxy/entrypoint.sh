#!/bin/bash
set -e

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Check if Pritunl profile is provided
if [ -z "$PRITUNL_PROFILE" ]; then
    log "No Pritunl profile specified. Running only as a reverse proxy."
else
    log "Connecting to Pritunl VPN using profile: $PRITUNL_PROFILE"
    
    # Check if the profile exists
    if [ ! -f "/conf/pritunl-profiles/$PRITUNL_PROFILE" ]; then
        log "Error: Profile /conf/pritunl-profiles/$PRITUNL_PROFILE not found!"
        exit 1
    fi

    log "Starting pritunl-client-service daemon..."
    pritunl-client-service &
    sleep 2

    
    # Import the profile
    pritunl-client add "/conf/pritunl-profiles/$PRITUNL_PROFILE"
    
    # Get the profile ID
    pritunl-client list
    PROFILE_ID=$(pritunl-client list | grep -E '\| [a-z0-9]{14,} ' | head -n1 | awk -F'|' '{gsub(/ /,"",$2); print $2}')
    
    if [ -z "$PROFILE_ID" ]; then
        log "Error: Failed to get profile ID for $PRITUNL_PROFILE | $PROFILE_ID"
        exit 1
    fi
    
    log "Starting Pritunl connection with profile ID: $PROFILE_ID"
    
    # Start the connection in the background
    pritunl-client start "$PROFILE_ID" &
    
    # Wait for the connection to establish
    log "Waiting for VPN connection to establish..."
    sleep 5
    
    # Check if the connection is established
    ATTEMPTS=0
    MAX_ATTEMPTS=12
    while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
        if pritunl-client list | grep -q "|.*Active.*|"; then
            log "VPN connection established successfully!"
            break
        fi
        ATTEMPTS=$((ATTEMPTS+1))
        log "Waiting for VPN connection... ($ATTEMPTS/$MAX_ATTEMPTS)"
        sleep 5
    done
    
    if [ $ATTEMPTS -eq $MAX_ATTEMPTS ]; then
        log "Error: Failed to establish VPN connection after multiple attempts."
        log "Current status:"
        pritunl-client list
        exit 1
    fi
fi

# --- Dynamic Nginx config generation ---
declare -A SERVER_BLOCKS

i=1
while true; do
    HOST_VAR="ROUTE_${i}_HOST"
    PATH_VAR="ROUTE_${i}_PATH"
    DEST_VAR="ROUTE_${i}_DESTINATION"
    PORT_VAR="ROUTE_${i}_PORT"

    [ -z "${!HOST_VAR}" ] && break

    ROUTE_HOST="${!HOST_VAR}"
    ROUTE_PATH="${!PATH_VAR:-/}"
    ROUTE_DEST="${!DEST_VAR}"
    ROUTE_PORT="${!PORT_VAR:-80}"

    log "Adding route: Host=$ROUTE_HOST Path=$ROUTE_PATH -> $ROUTE_DEST:$ROUTE_PORT"

    LOCATION_BLOCK="        location ${ROUTE_PATH} {
            proxy_pass http://${ROUTE_DEST}:${ROUTE_PORT};
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \"upgrade\" ;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
"
    SERVER_BLOCKS["$ROUTE_HOST"]+="$LOCATION_BLOCK"
    i=$((i+1))
done

# Build dynamic server blocks
DYNAMIC_SERVER_BLOCKS=""
for HOST in "${!SERVER_BLOCKS[@]}"; do
    DYNAMIC_SERVER_BLOCKS+="
    server {
        listen ${NGINX_PORT:-80};
        server_name $HOST;
${SERVER_BLOCKS[$HOST]}
    }"
done

log "Generating Nginx configuration..."

export DYNAMIC_SERVER_BLOCKS
export ADDITIONAL_ROUTES
export NGINX_PORT
export PROXY_PASS_DEFAULT
export PROXY_PORT_DEFAULT

# Use envsubst to replace the markers
envsubst '${NGINX_PORT} ${PROXY_PASS_DEFAULT} ${PROXY_PORT_DEFAULT} ${ADDITIONAL_ROUTES} ${DYNAMIC_SERVER_BLOCKS}' \
    < /etc/nginx/templates/nginx.conf.template > /etc/nginx/nginx.conf


# --- Dynamic Stream (TCP) Proxy Configuration ---
log "Generating TCP stream proxy configuration..."

STREAM_SERVER_BLOCKS=""
k=1
while true; do
    STREAM_HOST_VAR="STREAM_ROUTE_${k}_DESTINATION"
    STREAM_PORT_VAR="STREAM_ROUTE_${k}_PORT"
    STREAM_LISTEN_VAR="STREAM_ROUTE_${k}_LISTEN_PORT"
    STREAM_PROXY_PROTOCOL_VAR="STREAM_ROUTE_${k}_PROXY_PROTOCOL"
    STREAM_PROTOCOL_VAR="STREAM_ROUTE_${k}_PROTOCOL"


    [ -z "${!STREAM_HOST_VAR}" ] && break

    STREAM_DEST="${!STREAM_HOST_VAR}"
    STREAM_PORT="${!STREAM_PORT_VAR:-80}"
    STREAM_LISTEN="${!STREAM_LISTEN_VAR:-$STREAM_PORT}"  # Default listen = destination port
    STREAM_PROXY_PROTOCOL="${!STREAM_PROXY_PROTOCOL_VAR:-off}"
    STREAM_PROTOCOL="${!STREAM_PROTOCOL_VAR:-tcp}"

    if [ "$STREAM_PROTOCOL" = "udp" ]; then
        LISTEN_EXTRA=" udp"
    else
        LISTEN_EXTRA=""
    fi

    log "Adding stream route: 0.0.0.0:$STREAM_LISTEN -> $STREAM_DEST:$STREAM_PORT$LISTEN_EXTRA (proxy_protocol=$STREAM_PROXY_PROTOCOL)"

    STREAM_SERVER_BLOCKS+="
    server {
        listen ${STREAM_LISTEN}${LISTEN_EXTRA};
        proxy_pass ${STREAM_DEST}:${STREAM_PORT};
        proxy_protocol ${STREAM_PROXY_PROTOCOL};
    }
"
    k=$((k+1))
done

if [ -n "$STREAM_SERVER_BLOCKS" ]; then
    cat <<EOF > /etc/nginx/nginx.stream.conf
stream {
$STREAM_SERVER_BLOCKS
}
EOF
else
    log "No TCP stream routes defined."
fi


log "Final Nginx configuration:"
cat /etc/nginx/nginx.conf

log "Starting Nginx reverse proxy..."
nginx -g "daemon off;"