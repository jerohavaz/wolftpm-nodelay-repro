# Minimal fwTPM TCP_NODELAY reproduction

Compare pristine wolfTPM with the same server containing only the accepted-command-socket `TCP_NODELAY` change in `nodelay.patch`.

```bash
docker build -t wolftpm-nodelay-repro .
docker run --rm --network none wolftpm-nodelay-repro
```

Pins:

- wolfTPM: `d75a462faaccb5dfe3df1a4064ce80c178c6578e` (latest master)
- wolfSSL: `3c5eead44904df64e6a5a1f4ebdce377d35a849a` (v5.9.4-stable)