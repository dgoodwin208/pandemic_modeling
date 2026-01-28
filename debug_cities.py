import struct

def read_dbf(filename):
    with open(filename, 'rb') as f:
        numrec, header_size, record_size = struct.unpack('<xxxxLHH', f.read(12))
        f.seek(32)
        fields = []
        while True:
            field_data = f.read(32)
            if field_data[0] == 0x0D:
                break
            name = field_data[:11].rstrip(b'\x00').decode('latin-1')
            field_type = chr(field_data[11])
            field_size = field_data[16]
            fields.append((name, field_type, field_size))
        
        records = []
        for _ in range(numrec):
            record = {}
            f.read(1)
            for name, ftype, fsize in fields:
                value = f.read(fsize).decode('latin-1').strip()
                if ftype == 'N' and value:
                    try:
                        record[name] = float(value) if '.' in value else int(value)
                    except:
                        record[name] = 0
                else:
                    record[name] = value
            records.append(record)
        return records

records = read_dbf('frontend/public/data/ne_10m_populated_places_simple.dbf')

# Find some African cities
african_names = ['Lagos', 'Cairo', 'Nairobi', 'Johannesburg', 'Kinshasa', 'Addis Ababa']
print("Sample African cities:")
for r in records:
    if r.get('name') in african_names:
        print(f"  {r['name']}: iso_a2={r.get('iso_a2')!r}, adm0_a3={r.get('adm0_a3')!r}, pop_max={r.get('pop_max')}, adm0name={r.get('adm0name')!r}")

# Get unique iso_a2 values 
iso_values = set(r.get('iso_a2', '') for r in records)
print(f"\nSample iso_a2 values: {list(iso_values)[:20]}")

# Check for Nigeria entries
print("\nAll Nigerian cities (by adm0name):")
for r in records:
    if r.get('adm0name') == 'Nigeria':
        print(f"  {r['name']}: pop={r.get('pop_max')}")
