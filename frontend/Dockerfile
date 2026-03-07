# ===============================
# Etapa 1: Construcción (Build)
# ===============================
FROM node:20-alpine AS build
WORKDIR /app

# Instalar dependencias
COPY package*.json ./
RUN npm install

# Copiar el resto y empaquetar
COPY . .
RUN npm run build

# ===============================
# Etapa 2: Servidor (Producción)
# ===============================
FROM nginx:alpine

# Copiar configuración customizada de NGINX para React Router y Reverse Proxy (Backend)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copiar el paquete estático final
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
