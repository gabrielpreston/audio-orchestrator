FROM node:20-alpine

WORKDIR /app

# Install a small shell wrapper; we'll use npx at container start
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 9001

ENTRYPOINT ["/entrypoint.sh"]
