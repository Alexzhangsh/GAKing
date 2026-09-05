import bcrypt

hash = b"$2b$12$QzJ.xECwrmKWef1rpAjqeuu5/ymlyIiw1euDgp7I.H4q6myy17U66"
passwords = ["admin@12345", "admin123", "GAKing2026", "admin@123"]
for pwd in passwords:
    result = bcrypt.checkpw(pwd.encode(), hash)
    print(f"{pwd}: {result}")