import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from shared.config import JWT_SECRET
from shared.utils import encrypt_token, decrypt_token

print("JWT_SECRET type:", type(JWT_SECRET))
print("JWT_SECRET value:", JWT_SECRET)

org_id = "87165569-28aa-4d4d-8774-53ec5db15638"
order_id = "780fe618-ae87-4d4d-8774-53ec5db15638"

token = encrypt_token(org_id, order_id, str(JWT_SECRET))
print("Generated token:", token)

dec_org, dec_order = decrypt_token(token, str(JWT_SECRET))
print("Decrypted org_id:", dec_org)
print("Decrypted order_id:", dec_order)
assert dec_org == org_id
assert dec_order == order_id
print("Encryption & Decryption assertion passed successfully!")
