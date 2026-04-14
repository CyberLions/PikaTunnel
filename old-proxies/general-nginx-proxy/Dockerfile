FROM ubuntu:22.04

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install common dependencies
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    nginx \
    libnginx-mod-stream \
    gettext-base \
    openssl \
    # ^-- Added openssl for generating the default certificate
    python3 \
    iptables \
    net-tools \
    iproute2 \
    dnsutils \
    iputils-ping \
    procps \
    git \
    sudo

# Set up default Nginx configuration template
COPY general-nginx-proxy/nginx.conf.template /etc/nginx/templates/
COPY general-nginx-proxy/entrypoint.sh /entrypoint.sh

# Make the entrypoint script executable
RUN chmod +x /entrypoint.sh

# Clean up
RUN apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Default environment variables for Nginx listen ports
ENV NGINX_PORT="80"
ENV NGINX_HTTPS_PORT="443"

# Expose the Nginx ports
EXPOSE 80 443

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]