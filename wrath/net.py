import ctypes
import random
import struct

from trio import socket

from wrath.bpf import create_filter


IP_VERSION = 4
IP_IHL = 5
IP_DSCP = 0
IP_ECN = 0
IP_TOTAL_LEN = 40
IP_ID = 0x1337
IP_FLAGS = 0x2  # DF
IP_FRAGMENT_OFFSET = 0
IP_TTL = 255
IP_PROTOCOL = 6  # TCP
IP_CHECKSUM = 0
IP_SRC = '192.168.1.46'

TCP_SRC = 6969	# source port
TCP_ACK_NO = 0
TCP_DATA_OFFSET = 5
TCP_RESERVED = 0
TCP_NS = 0
TCP_CWR = 0
TCP_ECE = 0
TCP_URG = 0
TCP_ACK = 0
TCP_PSH = 0
TCP_RST = 0
TCP_SYN = 1
TCP_FIN = 0
TCP_WINDOW = 0x7110
TCP_CHECKSUM = 0
TCP_URG_PTR = 0


def create_send_sock():
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
    send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    return send_sock


def create_recv_sock(target):
    recv_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, 0x0800)
    fprog = create_filter(target)
    recv_sock.setsockopt(socket.SOL_SOCKET, 26, fprog)
    return recv_sock


def create_sock_pair(target, port):
    send_sock = create_send_sock()
    recv_sock = create_recv_sock(target, port)
    return send_sock, recv_sock


def checksum(header: bytes) -> int:
    checksum = 0
    for idx in range(0, len(header), 2):
        checksum += (header[idx] << 8) | header[idx + 1]
    checksum = (checksum >> 16) + (checksum & 0xffff)
    checksum = ~checksum & 0xffff
    return checksum


def build_ipv4_packet(target: str) -> bytes:
    src = socket.inet_aton(IP_SRC)
    dest = socket.inet_aton(target)

    size = struct.calcsize('!BBHHHBBH4s4s')
    assert size == 20

    buf = ctypes.create_string_buffer(size)

    struct.pack_into(
        '!BBHHHBBH4s4s',
        buf,
        0,
        (IP_VERSION << 4) | IP_IHL,
        IP_DSCP | IP_ECN,
        IP_TOTAL_LEN,
        IP_ID,
        (IP_FLAGS << 13) | IP_FRAGMENT_OFFSET,
        IP_TTL,
        IP_PROTOCOL,
        IP_CHECKSUM,
        src,
        dest
    )

    struct.pack_into(
        '!H',
        buf,
        10,
        checksum(bytes(buf))
    )

    return bytes(buf)


def build_tcp_packet(target, port: int) -> bytes:
    seq_no = random.randint(0, 2 ** 32 - 1)

    size = struct.calcsize('!HHIIBBHHH')
    assert size == 20

    buf = ctypes.create_string_buffer(size)

    struct.pack_into(
        '!HHIIHHHH',
        buf,
        0,
        TCP_SRC,
        port,
        seq_no,
        TCP_ACK_NO,
        (TCP_DATA_OFFSET << 12) | (TCP_RESERVED << 9) | (TCP_NS << 8) | (TCP_CWR << 7) | (TCP_ECE << 6) | (TCP_URG << 5) | (TCP_ACK << 4) | (TCP_PSH << 3) | (TCP_RST << 2) | (TCP_SYN << 1) | TCP_FIN,
        TCP_WINDOW,
        TCP_CHECKSUM,
        TCP_URG_PTR
    )

    tcp_pseudo_header = struct.pack(
        '!4s4sHHH',
        socket.inet_aton(IP_SRC),
        socket.inet_aton(target),
        0x6,
        len(buf),
        TCP_CHECKSUM
    )

    struct.pack_into('!H', buf, 16, checksum(tcp_pseudo_header + bytes(buf)))

    return bytes(buf)


def unpack(data):
    buf = ctypes.create_string_buffer(data[14:54], 40)
    unpacked = struct.unpack('!BBHHHBBH4s4sHHIIBBHHH', buf)
    src, flags = unpacked[10], unpacked[15]
    return src, flags