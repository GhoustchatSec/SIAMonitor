FROM node:22 as build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

# Статическая раздача через nginx-frontend внутри общего nginx? Можно прямо из nginx общего,
# но для простоты сложим артефакты в образ frontend:
FROM nginx:1.27-alpine
COPY --from=build /app/dist/ /usr/share/nginx/html
# Порт не публикуем наружу; доступ через общий reverse-proxy

