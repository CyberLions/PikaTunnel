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
    python3 \
    iptables \
    net-tools \
    iproute2 \
    dnsutils \
    iputils-ping \
    procps \
    git \
    sudo

# Architecture-specific installations
RUN arch=$(dpkg --print-architecture) && \
    if [ "$arch" = "amd64" ]; then \
        # AMD64 installation from repo
        echo "Installing Pritunl client for AMD64" && \
        echo "deb https://repo.pritunl.com/stable/apt noble main" > /etc/apt/sources.list.d/pritunl.list && \
        gpg --keyserver hkp://keyserver.ubuntu.com --recv-keys 7568D9BB55FF9E5287D586017AE645C0CF8E292A && \
        gpg --armor --export 7568D9BB55FF9E5287D586017AE645C0CF8E292A | tee /etc/apt/trusted.gpg.d/pritunl.asc && \
        apt-get update && \
        apt-get install -y pritunl-client-electron; \
    elif [ "$arch" = "arm64" ]; then \
        # ARM64 build from source
        echo "Building Pritunl client from source for ARM64" && \

        # Install golang
        curl -LO https://golang.org/dl/go1.22.2.linux-arm64.tar.gz && \
        tar -C /usr/local -xzf go1.22.2.linux-arm64.tar.gz && \
        export PATH=$PATH:/usr/local/go/bin && \
        go version && \

        # Use a specific version known to work instead of @latest
        go install github.com/pritunl/pritunl-client-electron/cli@latest && \
        go install github.com/pritunl/pritunl-client-electron/service@latest && \
        mkdir -p /root/go/bin && \
        cp /root/go/bin/service /usr/bin/pritunl-client-service && \
        cp /root/go/bin/cli /usr/bin/pritunl-client; \
    else \
        echo "Unsupported architecture: $arch" && \
        exit 1; \
    fi

# Install more dependencies
RUN apt-get update && apt-get install -y \
    openvpn 

# Create necessary directories
RUN mkdir -p /etc/nginx/templates /conf/pritunl-profiles /var/log/pritunl

# Set up default Nginx configuration template
COPY pritunl-nginx-proxy/nginx.conf.template /etc/nginx/templates/
COPY pritunl-nginx-proxy/entrypoint.sh /entrypoint.sh

# Make the entrypoint script executable
RUN chmod +x /entrypoint.sh

# Clean up
RUN apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Default environment variables
ENV PROXY_PASS_DEFAULT="10.0.103.2"
ENV PROXY_PORT_DEFAULT="80"
ENV PRITUNL_PROFILE="cloud"
ENV NGINX_PORT="80"

# Expose the Nginx port
EXPOSE 80 443

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]
