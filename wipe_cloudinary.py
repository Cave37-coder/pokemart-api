import cloudinary
import cloudinary.api

cloudinary.config(
    cloud_name = "dpdulaufd",
    api_key    = "613679581116384",
    api_secret = "nIcFekH7wHLFfOKpkIX7dPERQ_A",
    secure     = True
)

print("Deleting all assets in pokebulk/cards folder...")
deleted = 0
while True:
    result = cloudinary.api.delete_resources_by_prefix("pokebulk/cards/", max_results=500)
    count = len(result.get("deleted", {}))
    deleted += count
    print(f"  Deleted batch: {count} | Total: {deleted}")
    if count < 500:
        break

# Also delete the folder itself
try:
    cloudinary.api.delete_folder("pokebulk/cards")
    cloudinary.api.delete_folder("pokebulk")
    print("Folders deleted.")
except Exception as e:
    print(f"Folder delete: {e}")

print(f"Done. Total deleted: {deleted}")
