FROM nginx:1.27-alpine
RUN apk add --no-cache python3
WORKDIR /opt/gateway
COPY discovery.py entrypoint.sh ./
COPY docs ./docs
COPY nginx.conf /etc/nginx/nginx.conf
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=10s --timeout=3s CMD wget -q -O /dev/null http://127.0.0.1/health/ || exit 1
ENTRYPOINT ["/opt/gateway/entrypoint.sh"]
