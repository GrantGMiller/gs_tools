import aes_tools

open('key.dat', mode='wb').write(aes_tools.GetRandomKey())

c = aes_tools.AES_Cipher()
c.en