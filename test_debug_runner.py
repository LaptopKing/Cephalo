import traceback
from symbol_extractor import CodeSymbolIndexer

idx = CodeSymbolIndexer()
print("Starting file walk...")
for f in idx._walk_source_files(idx.root_dir):
    print("Testing file:", f.name)
    try:
        s = idx.extract_symbols_from_file(f)
        print("  -> Got", len(s), "symbols")
    except Exception as e:
        print("  ERROR on", f.name)
        traceback.print_exc()
print("Finished!")
