FROM postgres:17-alpine
RUN apk add --no-cache rclone tzdata
COPY backup.sh restore-test.sh entrypoint.sh /scripts/
RUN chmod +x /scripts/*.sh
ENTRYPOINT ["/scripts/entrypoint.sh"]
