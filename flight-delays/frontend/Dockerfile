FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf.template
COPY entrypoint.sh /entrypoint.sh
RUN rm -f /etc/nginx/conf.d/default.conf \
  && sed -i 's/\r$//' /entrypoint.sh \
  && chmod +x /entrypoint.sh
EXPOSE 80
CMD ["/entrypoint.sh"]
