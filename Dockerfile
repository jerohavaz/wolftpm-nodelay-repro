FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates clang cmake git ninja-build pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

# Same dependency pins as the confirmed reproduction.
RUN git init /src/wolfssl \
    && git -C /src/wolfssl fetch --depth 1 https://github.com/wolfSSL/wolfssl.git \
        3c5eead44904df64e6a5a1f4ebdce377d35a849a \
    && git -C /src/wolfssl -c core.autocrlf=false checkout --detach FETCH_HEAD \
    && cmake -S /src/wolfssl -B /build/wolfssl -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang \
        -DCMAKE_C_FLAGS=-DWC_RSA_NO_PADDING -DCMAKE_INSTALL_PREFIX=/opt/wolfssl \
        -DBUILD_SHARED_LIBS=ON -DWOLFSSL_CRYPT_TESTS=no -DWOLFSSL_EXAMPLES=no \
        -DWOLFSSL_KEYGEN=yes -DWOLFSSL_PKCALLBACKS=yes -DWOLFSSL_TPM=yes \
        -DWOLFSSL_MLDSA=yes -DWOLFSSL_MLKEM=yes \
    && cmake --build /build/wolfssl --parallel 2 \
    && cmake --install /build/wolfssl

RUN git init /src/pristine \
    && git -C /src/pristine fetch --depth 1 https://github.com/wolfSSL/wolfTPM.git \
        d75a462faaccb5dfe3df1a4064ce80c178c6578e \
    && git -C /src/pristine -c core.autocrlf=false checkout --detach FETCH_HEAD \
    && cp -a /src/pristine /src/nodelay
COPY nodelay.patch /tmp/nodelay.patch
RUN git -C /src/nodelay apply --check /tmp/nodelay.patch \
    && git -C /src/nodelay apply /tmp/nodelay.patch

RUN for variant in pristine nodelay; do \
      cmake -S /src/${variant} -B /build/${variant} -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang \
        -DCMAKE_PREFIX_PATH=/opt/wolfssl -DWITH_WOLFSSL=/opt/wolfssl \
        -DWOLFTPM_EXAMPLES=no -DWOLFTPM_FWTPM=yes -DWOLFTPM_INTERFACE=SWTPM \
        '-DCMAKE_C_FLAGS=-D_DEFAULT_SOURCE -DWOLFTPM_V185 -DWOLFTPM_PQC -DWOLFTPM_MLDSA -DWOLFTPM_MLKEM' \
      && cmake --build /build/${variant} --target fwtpm_server --parallel 2 \
      || exit 1; \
    done

COPY test.py /test.py
ENV LD_LIBRARY_PATH=/opt/wolfssl/lib:/opt/wolfssl/lib64
ENTRYPOINT ["python3", "/test.py"]
