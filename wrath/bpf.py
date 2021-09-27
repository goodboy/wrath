import ctypes
import struct


buf = None


def create_filter():
    BPF_FILTER = [
        [ 0x28, 0, 0, 0x0000000c ],
        [ 0x15, 0, 12, 0x00000800 ],
        [ 0x20, 0, 0, 0x0000001a ],
        [ 0x15, 0, 10, 0xc0a80101 ],
        [ 0x30, 0, 0, 0x00000017 ],
        [ 0x15, 2, 0, 0x00000084 ],
        [ 0x15, 1, 0, 0x00000006 ],
        [ 0x15, 0, 6, 0x00000011 ],
        [ 0x28, 0, 0, 0x00000014 ],
        [ 0x45, 4, 0, 0x00001fff ],
        [ 0xb1, 0, 0, 0x0000000e ],
        [ 0x48, 0, 0, 0x00000010 ],
        [ 0x15, 0, 1, 0x00001b39 ],
        [ 0x6, 0, 0, 0x00040000 ],
        [ 0x6, 0, 0, 0x00000000 ],
    ]

    filters = [struct.pack('HBBI', *x) for x in BPF_FILTER]
    filters = b''.join(x for x in filters)

    global buf
    buf = ctypes.create_string_buffer(filters)

    mem_addr_of_filters = ctypes.addressof(buf)

    fprog = struct.pack('HL', len(BPF_FILTER), mem_addr_of_filters)
    return fprog