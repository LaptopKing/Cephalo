import sys
print("STEP 1: python started")
try:
    import symbol_extractor
    print("STEP 2: symbol_extractor imported")
    idx = symbol_extractor.CodeSymbolIndexer()
    print("STEP 3: indexer initialized, root:", idx.root_dir)
    files = list(idx._walk_source_files(idx.root_dir))
    print(f"STEP 4: found {len(files)} files")
    for f in files[:5]:
        print("Parsing:", f.name)
        s = idx.extract_symbols_from_file(f)
        print("  -> Got", len(s), "symbols")
except BaseException as e:
    import traceback
    print("CAUGHT EXCEPTION:", e)
    traceback.print_exc()
print("STEP 5: done")
