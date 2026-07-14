# test_cache_direct.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from market_cache import update_market_cache

print("=" * 60)
print("Running cache update directly...")
print("=" * 60)

try:
    update_market_cache()
    print("\n✅ Cache update completed successfully!")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()