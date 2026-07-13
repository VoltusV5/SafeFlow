FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && \
    apt-get install -y software-properties-common wget unzip iptables iproute2 python3 python3-pip && \
    add-apt-repository -y ppa:amnezia/ppa && \
    apt-get update && \
    apt-get install -y amneziawg-tools

# Download xray binary for CLI API calls
RUN wget -O xray.zip https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip && \
    unzip xray.zip xray -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/xray && \
    rm xray.zip

COPY requirements.txt .
# Use --break-system-packages for Ubuntu > 22.04 or when forced. For 22.04, it might not be needed, but we'll use it if pip complains, or just install globally
RUN pip3 install --no-cache-dir -r requirements.txt || pip3 install --no-cache-dir -r requirements.txt --break-system-packages

COPY . .

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
