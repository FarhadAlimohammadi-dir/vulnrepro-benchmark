FROM php:8.1-apache

RUN docker-php-ext-install pdo pdo_mysql

COPY app/ /var/www/html/
RUN mkdir -p /var/www/html/views /var/www/html/services /var/www/html/utils

RUN a2enmod rewrite && \
    echo "ServerName localhost" >> /etc/apache2/apache2.conf

EXPOSE 80