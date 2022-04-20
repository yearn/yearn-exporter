#! /bin/bash
set -e

rm *.pem *.srl || true

CN=${CN:-localhost}

# 1. generate ca private key and self-signed certificate
openssl req -x509 -newkey rsa:4096 -days 3650 -nodes -keyout ca-key.pem -out ca-cert.pem -subj "/CN=$CN/"

# 2. generate server private key and certificate signing request (csr)
openssl req -newkey rsa:4096 -nodes -keyout server-key.pem -out server-req.pem -subj "/CN=$CN/"

# 3. sign server csr and get back the signed certificate
openssl x509 -req -in server-req.pem -days 3650 -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial -out server-cert.pem

# 4. cleanup
rm ca-key.pem ca-cert.pem server-req.pem ca-cert.srl || true
