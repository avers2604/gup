"""Portable password protected backups using scrypt and AES-256-GCM."""
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.exceptions import InvalidTag
from .atomic import atomic_output

MAGIC = b"GETBACKUP1"
MAX_SIZE = 256 * 1024**2


def _key(password, salt):
    if not password:
        raise ValueError("Введите пароль резервной копии")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def encrypt(source, destination, password):
    if len(password) < 12:
        raise ValueError("Пароль должен содержать не менее 12 символов")
    if os.path.getsize(source) > MAX_SIZE:
        raise ValueError("Зашифрованная копия ограничена 256 МБ; используйте ZIP на защищённом носителе")
    salt, nonce = os.urandom(16), os.urandom(12)
    header = MAGIC + salt + nonce
    with open(source, "rb") as stream:
        ciphertext = AESGCM(_key(password, salt)).encrypt(nonce, stream.read(), header)
    with atomic_output(destination) as temporary, open(temporary, "wb") as stream:
        stream.write(header + ciphertext)


def decrypt(source, destination, password):
    if os.path.getsize(source) > MAX_SIZE + 128:
        raise ValueError("Архив слишком большой")
    with open(source, "rb") as stream:
        header = stream.read(len(MAGIC) + 28)
        ciphertext = stream.read()
    if not header.startswith(MAGIC) or len(header) != len(MAGIC) + 28:
        raise ValueError("Неверный формат копии")
    salt, nonce = header[len(MAGIC):len(MAGIC) + 16], header[-12:]
    try:
        plain = AESGCM(_key(password, salt)).decrypt(nonce, ciphertext, header)
    except InvalidTag:
        raise ValueError("Неверный пароль или повреждённая копия") from None
    with open(destination, "wb") as stream:
        stream.write(plain)
