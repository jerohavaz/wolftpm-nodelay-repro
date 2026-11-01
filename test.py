"""Ten successful GetRandom requests per server; print median TCP latency."""

import socket
import statistics
import struct
import subprocess
import tempfile
import time


def receive(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise RuntimeError("Unexpected EOF")
        data.extend(chunk)
    return bytes(data)


def command(sock, code, parameter):
    request = struct.pack(">HIIH", 0x8001, 12, code, parameter)
    # One packed MSSIM request; client-side Nagle is disabled separately.
    frame = struct.pack(">IBI", 8, 0, len(request)) + request
    start = time.perf_counter_ns()
    sock.sendall(frame)
    size = struct.unpack(">I", receive(sock, 4))[0]
    if not 10 <= size <= 4096:
        raise RuntimeError(f"Invalid response size: {size}")
    response = receive(sock, size)
    ack = struct.unpack(">I", receive(sock, 4))[0]
    elapsed_ms = (time.perf_counter_ns() - start) / 1e6
    tag, length, rc = struct.unpack(">HII", response[:10])
    if ack or rc or tag != 0x8001 or length != size:
        raise RuntimeError(f"Invalid response: TPM rc={rc:#x}, MSSIM ack={ack}")
    if code == 0x17B:
        if len(response) < 12:
            raise RuntimeError("Truncated GetRandom response")
        count = struct.unpack(">H", response[10:12])[0]
        if not 0 < count <= parameter or len(response) != 12 + count:
            raise RuntimeError("Invalid GetRandom payload")
    return elapsed_ms


def test(variant):
    with tempfile.TemporaryDirectory() as state, tempfile.TemporaryFile() as log:
        server = subprocess.Popen(
            [f"/build/{variant}/bin/fwtpm_server", "--port", "2321",
             "--platform-port", "2322", "--clear"],
            cwd=state, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 15
            while True:
                if server.poll() is not None or time.monotonic() >= deadline:
                    log.seek(0)
                    raise RuntimeError("Server did not start:\n" + log.read().decode(errors="replace"))
                try:
                    sock = socket.create_connection(("127.0.0.1", 2321), timeout=5)
                    break
                except ConnectionRefusedError:
                    time.sleep(0.05)
            with sock:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                command(sock, 0x144, 0)  # TPM2_Startup(CLEAR)
                command(sock, 0x17B, 32)  # One warm-up GetRandom
                values = [command(sock, 0x17B, 32) for _ in range(10)]
            median = statistics.median(values)
            print(f"{variant:8s}: {median:.3f} ms median (10 successful requests)", flush=True)
            return median
        finally:
            if server.poll() is None:
                server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
                raise RuntimeError("Server did not shut down")
            if server.returncode != 0:
                raise RuntimeError(f"Server exited with {server.returncode}")


if __name__ == "__main__":
    pristine = test("pristine")
    nodelay = test("nodelay")
    print(f"Median ratio: {pristine / max(nodelay, 1e-9):.1f}x")