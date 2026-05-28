with open('users/serializers.py', 'r') as f:
    content = f.read()

# Find RegisterSerializer and update fields
old = "        fields = ['id', 'username', 'email', 'password', 'trainer_level']\n        read_only_fields = ['id', 'trainer_level']"
new = "        fields = ['id', 'username', 'email', 'password', 'trainer_level', 'first_name', 'last_name', 'phone_number', 'address_line1', 'address_line2', 'address_city', 'address_province', 'address_postal_code', 'pudo_locker_name', 'pudo_locker_address']\n        read_only_fields = ['id', 'trainer_level']"

if old in content:
    content = content.replace(old, new)
    print("Register serializer fields updated")
else:
    print("NOT FOUND")

with open('users/serializers.py', 'w') as f:
    f.write(content)
