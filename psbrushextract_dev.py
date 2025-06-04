#!/usr/bin/env python3
# Author: Morrow Shore
# License: AGPLv3
# Contact: inquiry@morrowshore.com

import struct

def parse_brush_parameters(data):

    
    results = []
    L = len(data)
    
    pos = data.find(b'Objc')
    if pos == -1:
        return results  
    
    type_markers = {
        b'UntF': 'UntF',
        b'bool': 'bool',
        b'long': 'long',
        b'doub': 'doub',
        b'enum': 'enum',
        b'TEXT': 'TEXT', 
        b'Objc': 'Objc', 
        b'VlLs': 'VlLs'  
    }
    
    def find_printable_key_before(data, pos, max_lookback=50):
        """Extract the parameter name before a type marker"""
        start = max(0, pos - max_lookback)
        segment = data[start:pos]
        
        key = ""
        for i in range(len(segment) - 1, -1, -1):
            if 32 <= segment[i] <= 126:  
                key = chr(segment[i]) + key
            else:
                break
        
        return key.strip()
    
    while pos < L - 4:
        found_marker = False
        
        for marker_bytes, marker_name in type_markers.items():
            if data[pos:pos+len(marker_bytes)] == marker_bytes:
                key = find_printable_key_before(data, pos)
                
                if marker_name == 'TEXT':
                    if pos + 8 <= L:
                        length = struct.unpack('>I', data[pos+4:pos+8])[0]
                        text_start = pos + 8
                        text_end = min(text_start + length * 2, L)
                        try:
                            text = data[text_start:text_end].decode('utf-16-be').rstrip('\x00')
                        except:
                            text = data[text_start:text_end].decode('utf-8', errors='replace').rstrip('\x00')
                        results.append((key, 'TEXT', text))
                        pos = text_end
                        found_marker = True
                        break
                
                elif marker_name == 'UntF':
                    if pos + 18 <= L:
                        unit_code = data[pos+4:pos+8].decode('ascii', errors='ignore').strip()
                        # 8-byte double 
                        val = struct.unpack('>d', data[pos+8:pos+16])[0]
                        results.append((key, f'UntF#{unit_code}', val))
                        pos += 18
                        found_marker = True
                        break
                
                elif marker_name == 'long':
                    if pos + 8 <= L:
                        val = struct.unpack('>i', data[pos+4:pos+8])[0]
                        results.append((key, 'long', val))
                        pos += 8
                        found_marker = True
                        break
                
                elif marker_name == 'bool':
                    if pos + 5 <= L:
                        val = bool(data[pos+4])
                        results.append((key, 'bool', val))
                        pos += 5
                        found_marker = True
                        break
                
                elif marker_name == 'doub':
                    if pos + 12 <= L:
                        val = struct.unpack('>d', data[pos+4:pos+12])[0]
                        results.append((key, 'doub', val))
                        pos += 12
                        found_marker = True
                        break
                
                elif marker_name == 'enum':
                    if pos + 8 <= L:
                        enum_val = data[pos+4:pos+8].decode('ascii', errors='ignore').rstrip('\x00')
                        # Find next marker to get full binary data
                        next_pos = pos + 8
                        for next_marker in type_markers.keys():
                            found_next = data.find(next_marker, next_pos)
                            if found_next != -1:
                                next_pos = min(next_pos, found_next) if next_pos == pos + 8 else min(next_pos, found_next)
                        binary_hex = data[pos+4:next_pos].hex()
                        results.append((key, 'enum', f"{enum_val} (0x{binary_hex})"))
                        pos = next_pos if next_pos > pos + 8 else pos + 8
                        found_marker = True
                        break
                
                elif marker_name == 'Objc':
                    # Find next marker to get full binary data
                    next_pos = L
                    for next_marker in type_markers.keys():
                        found_next = data.find(next_marker, pos + 4)
                        if found_next != -1:
                            next_pos = min(next_pos, found_next)
                    binary_hex = data[pos:next_pos].hex()
                    results.append((key, 'Objc', f"skipped (0x{binary_hex})"))
                    pos = next_pos
                    found_marker = True
                    break
                
                elif marker_name == 'VlLs':
                    # Find next marker to get full binary data
                    next_pos = L
                    for next_marker in type_markers.keys():
                        found_next = data.find(next_marker, pos + 4)
                        if found_next != -1:
                            next_pos = min(next_pos, found_next)
                    binary_hex = data[pos:next_pos].hex()
                    results.append((key, 'VlLs', f"skipped (0x{binary_hex})"))
                    pos = next_pos
                    found_marker = True
                    break
        
        if not found_marker:
            pos += 1
    
    return results

def format_results(results, indent=0):
    output = []
    
    for key, param_type, value in results:
        output.append(f"{key:<30}\t{param_type:<15}\t{value}")
    
    return '\n'.join(output)

if __name__ == "__main__":
    import sys
    import os
    
    if len(sys.argv) != 2:
        print("Usage: python test2.py <brush_file.abr>")
        sys.exit(1)
    
    filename = sys.argv[1]
    output_dir = os.path.dirname(filename)
    brush_name = os.path.splitext(os.path.basename(filename))[0]
    output_filename = os.path.join(output_dir, f"{brush_name}_dump.txt")
    
    try:
        with open(filename, 'rb') as f:
            data = f.read()
        
        results = parse_brush_parameters(data)
        formatted = format_results(results)
        
        with open(output_filename, 'w', encoding='utf-8') as out_file:
            out_file.write(f"Parsed {filename}\n")
            out_file.write(f"\n")
            out_file.write(f"Tool by Morrow Shore https://morrowshore.com\n")
            out_file.write(f"\n")
            out_file.write("-" * 50 + "\n")
            out_file.write(formatted)
        
        print(f"Successfully exported results to {output_filename}")
        
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)