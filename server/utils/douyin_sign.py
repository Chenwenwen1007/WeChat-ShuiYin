import math
import random
import struct
import time


# ============ RC4 加密 ============
def rc4_encrypt(plaintext: str | bytes, key: str | bytes) -> str:
    """RC4流加密"""
    if isinstance(plaintext, str):
        plaintext = [ord(c) for c in plaintext]
    else:
        plaintext = list(plaintext)

    if isinstance(key, str):
        key = [ord(c) for c in key]
    else:
        key = list(key)

    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]

    i = 0
    j = 0
    cipher = []
    for k in range(len(plaintext)):
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        t = (s[i] + s[j]) % 256
        cipher.append(chr(s[t] ^ plaintext[k]))
    return "".join(cipher)


# ============ SM3 哈希算法 ============
def _le(e: int, r: int) -> int:
    """循环左移"""
    return ((e << (r % 32)) | (e >> (32 - (r % 32)))) & 0xFFFFFFFF


def _de(e: int) -> int:
    """SM3常量Tj"""
    if 0 <= e < 16:
        return 2043430169
    if 16 <= e < 64:
        return 2055708042
    raise ValueError("invalid j for constant Tj")


def _pe(e: int, r: int, t: int, n: int) -> int:
    """SM3布尔函数FF"""
    if 0 <= e < 16:
        return (r ^ t ^ n) & 0xFFFFFFFF
    if 16 <= e < 64:
        return ((r & t) | (r & n) | (t & n)) & 0xFFFFFFFF
    raise ValueError("invalid j for bool function FF")


def _he(e: int, r: int, t: int, n: int) -> int:
    """SM3布尔函数GG"""
    if 0 <= e < 16:
        return (r ^ t ^ n) & 0xFFFFFFFF
    if 16 <= e < 64:
        return ((r & t) | ((~r) & n)) & 0xFFFFFFFF
    raise ValueError("invalid j for bool function GG")


def _se(value: str, width: int, fill: str) -> str:
    """字符串填充"""
    output = str(value)
    while len(output) < width:
        output = fill + output
    return output


class SM3:
    """SM3哈希算法实现（对应JS中的SM3类）"""

    def __init__(self):
        self.reg = []
        self.chunk = []
        self.size = 0
        self.reset()

    def reset(self):
        self.reg = [
            1937774191, 1226093241, 388252375, 3666478592,
            2842636476, 372324522, 3817729613, 2969243214,
        ]
        self.chunk = []
        self.size = 0

    def write(self, input_data: str | list):
        if isinstance(input_data, str):
            # 编码为字节
            encoded = []
            for ch in input_data:
                code = ord(ch)
                if code < 0x80:
                    encoded.append(code)
                else:
                    # UTF-8编码
                    if code < 0x800:
                        encoded.append(0xC0 | (code >> 6))
                        encoded.append(0x80 | (code & 0x3F))
                    else:
                        encoded.append(0xE0 | (code >> 12))
                        encoded.append(0x80 | ((code >> 6) & 0x3F))
                        encoded.append(0x80 | (code & 0x3F))
            bytes_data = encoded
        else:
            bytes_data = list(input_data)

        self.size += len(bytes_data)
        free = 64 - len(self.chunk)

        if len(bytes_data) < free:
            self.chunk = self.chunk + bytes_data
            return

        self.chunk = self.chunk + bytes_data[:free]
        while len(self.chunk) >= 64:
            self._compress(self.chunk)
            if free < len(bytes_data):
                self.chunk = bytes_data[free:min(free + 64, len(bytes_data))]
            else:
                self.chunk = []
            free += 64

    def sum(self, input_data=None, fmt=None):
        if input_data is not None:
            self.reset()
            self.write(input_data)

        self._fill()

        for i in range(0, len(self.chunk), 64):
            self._compress(self.chunk[i:i + 64])

        if fmt == "hex":
            result = ""
            for i in range(8):
                result += _se(format(self.reg[i], "x"), 8, "0")
            self.reset()
            return result
        else:
            result = [0] * 32
            for i in range(8):
                c = self.reg[i]
                result[4 * i + 3] = c & 255
                c >>= 8
                result[4 * i + 2] = c & 255
                c >>= 8
                result[4 * i + 1] = c & 255
                c >>= 8
                result[4 * i] = c & 255
            self.reset()
            return result

    def _compress(self, t: list):
        if len(t) < 64:
            raise ValueError("compress error: not enough data")

        w = [0] * 132
        for i in range(16):
            w[i] = ((t[4 * i] << 24) | (t[4 * i + 1] << 16) | (t[4 * i + 2] << 8) | t[4 * i + 3]) & 0xFFFFFFFF

        for i in range(16, 68):
            a = w[i - 16] ^ w[i - 9] ^ _le(w[i - 3], 15)
            a = a ^ _le(a, 15) ^ _le(a, 23)
            w[i] = (a ^ _le(w[i - 13], 7) ^ w[i - 6]) & 0xFFFFFFFF

        for i in range(64):
            w[i + 68] = (w[i] ^ w[i + 4]) & 0xFFFFFFFF

        state = list(self.reg)
        for i in range(64):
            ss1 = _le((((_le(state[0], 12) + state[4] + _le(_de(i), i)) & 0xFFFFFFFF) & 0xFFFFFFFF), 7)
            ss2 = (ss1 ^ _le(state[0], 12)) & 0xFFFFFFFF
            tt1 = (_pe(i, state[0], state[1], state[2]) + state[3] + ss2 + w[i + 68]) & 0xFFFFFFFF
            tt2 = (_he(i, state[4], state[5], state[6]) + state[7] + ss1 + w[i]) & 0xFFFFFFFF

            state[3] = state[2]
            state[2] = _le(state[1], 9)
            state[1] = state[0]
            state[0] = tt1
            state[7] = state[6]
            state[6] = _le(state[5], 19)
            state[5] = state[4]
            state[4] = (tt2 ^ _le(tt2, 9) ^ _le(tt2, 17)) & 0xFFFFFFFF

        for i in range(8):
            self.reg[i] = (self.reg[i] ^ state[i]) & 0xFFFFFFFF

    def _fill(self):
        total_bits = 8 * self.size
        mod = (len(self.chunk) + 1) % 64
        self.chunk.append(128)

        if 64 - mod < 8:
            mod -= 64

        while mod < 56:
            self.chunk.append(0)
            mod += 1

        high = total_bits // 4294967296
        for i in range(4):
            self.chunk.append((high >> (8 * (3 - i))) & 255)
        for i in range(4):
            self.chunk.append((total_bits >> (8 * (3 - i))) & 255)


# ============ Base64变体编码 ============
def result_encrypt(long_str: str, num=None) -> str:
    """抖音自定义Base64变体编码"""
    s_obj = {
        "s0": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",
        "s1": "Dkdpgh4ZKsQB80/Mfvw36XI1R25+WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
        "s2": "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
        "s3": "ckdp1h4ZKsUB80/Mfvw36XIgR25+WQAlEi7NLboqYTOPuzmFjJnryx9HVGDaStCe",
        "s4": "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe",
    }

    constant = {
        0: 16515072,
        1: 258048,
        2: 4032,
        "str": s_obj.get(f"s{num}", s_obj["s0"]),
    }

    result = ""
    round_num = 0
    long_int = _get_long_int(round_num, long_str)

    for i in range((len(long_str) // 3) * 4):
        if i // 4 != round_num:
            round_num += 1
            long_int = _get_long_int(round_num, long_str)

        key = i % 4
        temp_int = 0
        if key == 0:
            temp_int = (long_int & constant[0]) >> 18
            result += constant["str"][temp_int]
        elif key == 1:
            temp_int = (long_int & constant[1]) >> 12
            result += constant["str"][temp_int]
        elif key == 2:
            temp_int = (long_int & constant[2]) >> 6
            result += constant["str"][temp_int]
        elif key == 3:
            temp_int = long_int & 63
            result += constant["str"][temp_int]

    return result


def _get_long_int(round_num: int, long_str: str) -> int:
    offset = round_num * 3
    return (ord(long_str[offset]) << 16) | (ord(long_str[offset + 1]) << 8) | ord(long_str[offset + 2])


# ============ 随机生成 ============
def gener_random(random_val: float, option: list) -> list:
    r = int(random_val) & 0xFFFF
    return [
        ((r & 255 & 170) | (option[0] & 85)) & 0xFF,
        ((r & 255 & 85) | (option[0] & 170)) & 0xFF,
        (((r >> 8) & 255 & 170) | (option[1] & 85)) & 0xFF,
        (((r >> 8) & 255 & 85) | (option[1] & 170)) & 0xFF,
    ]


def generate_random_str() -> str:
    random_str_list = []
    random_str_list.extend(gener_random(random.random() * 10000, [3, 45]))
    random_str_list.extend(gener_random(random.random() * 10000, [1, 0]))
    random_str_list.extend(gener_random(random.random() * 10000, [1, 5]))
    return "".join(chr(c) for c in random_str_list)


# ============ 核心签名生成 ============
def generate_rc4_bb_str(
    url_search_params: str,
    user_agent: str,
    window_env_str: str = "1536|747|1536|834|0|30|0|0|1536|834|1536|864|1525|747|24|24|Win32",
    suffix: str = "cus",
    arguments: list = None,
) -> str:
    if arguments is None:
        arguments = [0, 1, 14]

    sm3 = SM3()
    start_time = int(time.time() * 1000)

    url_search_params_list = sm3.sum(sm3.sum(url_search_params + suffix))
    cus = sm3.sum(sm3.sum(suffix))

    # 对UA进行RC4加密后再SM3哈希
    ua_rc4 = rc4_encrypt(user_agent, bytes([0, 1, 14]))
    ua_encrypted = result_encrypt(ua_rc4, "s3")
    ua = sm3.sum(ua_encrypted)

    end_time = int(time.time() * 1000)

    b = {
        8: 3,
        10: end_time,
        15: {
            "aid": 6383,
            "pageId": 6241,
            "boe": False,
            "ddrt": 7,
            "paths": {"include": [{}, {}, {}, {}, {}, {}, {}], "exclude": []},
            "track": {"mode": 0, "delay": 300, "paths": []},
            "dump": True,
            "rpU": "",
        },
        16: start_time,
        18: 44,
        19: [1, 0, 1, 5],
    }

    b[20] = (b[16] >> 24) & 255
    b[21] = (b[16] >> 16) & 255
    b[22] = (b[16] >> 8) & 255
    b[23] = b[16] & 255
    b[24] = math.floor(b[16] / 256 / 256 / 256 / 256)
    b[25] = math.floor(b[16] / 256 / 256 / 256 / 256 / 256)

    b[26] = (arguments[0] >> 24) & 255
    b[27] = (arguments[0] >> 16) & 255
    b[28] = (arguments[0] >> 8) & 255
    b[29] = arguments[0] & 255

    b[30] = math.floor(arguments[1] / 256) & 255
    b[31] = arguments[1] % 256
    b[32] = (arguments[1] >> 24) & 255
    b[33] = (arguments[1] >> 16) & 255

    b[34] = (arguments[2] >> 24) & 255
    b[35] = (arguments[2] >> 16) & 255
    b[36] = (arguments[2] >> 8) & 255
    b[37] = arguments[2] & 255

    b[38] = url_search_params_list[21]
    b[39] = url_search_params_list[22]
    b[40] = cus[21]
    b[41] = cus[22]
    b[42] = ua[23]
    b[43] = ua[24]

    b[44] = (b[10] >> 24) & 255
    b[45] = (b[10] >> 16) & 255
    b[46] = (b[10] >> 8) & 255
    b[47] = b[10] & 255
    b[48] = b[8]
    b[49] = math.floor(b[10] / 256 / 256 / 256 / 256)
    b[50] = math.floor(b[10] / 256 / 256 / 256 / 256 / 256)

    b[51] = b[15]["pageId"]
    b[52] = (b[15]["pageId"] >> 24) & 255
    b[53] = (b[15]["pageId"] >> 16) & 255
    b[54] = (b[15]["pageId"] >> 8) & 255
    b[55] = b[15]["pageId"] & 255

    b[56] = b[15]["aid"]
    b[57] = b[15]["aid"] & 255
    b[58] = (b[15]["aid"] >> 8) & 255
    b[59] = (b[15]["aid"] >> 16) & 255
    b[60] = (b[15]["aid"] >> 24) & 255

    window_env_list = [ord(c) for c in window_env_str]
    b[64] = len(window_env_list)
    b[65] = b[64] & 255
    b[66] = (b[64] >> 8) & 255

    b[69] = 0
    b[70] = 0
    b[71] = 0

    xor_keys = [
        18, 20, 52, 26, 30, 34, 58, 38, 40, 53, 42, 21,
        27, 54, 55, 31, 35, 57, 39, 41, 43, 22, 28, 32,
        60, 36, 23, 29, 33, 37, 44, 45, 59, 46, 47, 48,
        49, 50, 24, 25, 65, 66, 70, 71,
    ]
    b[72] = 0
    for k in xor_keys:
        b[72] ^= b[k]

    bb = [b[k] for k in xor_keys]
    bb = bb + window_env_list + [b[72]]
    # 模拟JavaScript的String.fromCharCode行为（自动取模65536）
    bb_str = "".join(chr(c & 0xFFFF) for c in bb)
    return rc4_encrypt(bb_str, chr(121))


def generate_a_bogus(url_search_params: str, user_agent: str) -> str:
    """
    生成抖音Web API所需的a_bogus签名参数
    """
    result_str = generate_random_str() + generate_rc4_bb_str(url_search_params, user_agent)
    return result_encrypt(result_str, "s4") + "="
