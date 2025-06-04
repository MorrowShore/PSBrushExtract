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
        b'UntF': 'UntF', # contains values - done
        b'bool': 'bool', # contains values - done
        b'long': 'long', # contains values - done
        b'doub': 'doub', # contains values - probably done
        b'enum': 'enum', # contains modes - done
        b'TEXT': 'TEXT', # contains text - done
        b'Objc': 'Objc', # indicator of a set containing curves & dynamics - not fully done
        b'VlLs': 'VlLs'  # ?
    }
    
    def find_printable_key_before(data, pos, max_lookback=50):
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
                    if pos + 12 <= L:
                        enum_type = data[pos+8:pos+12].decode('ascii', errors='ignore').rstrip('\x00')
                        if not enum_type:
                            enum_type = data[pos+4:pos+8].decode('ascii', errors='ignore').rstrip('\x00')
                        
                        enum_pos = pos + 12
                        while enum_pos < L and data[enum_pos] in [0, 32]:
                            enum_pos += 1
                        
                        enum_value = ""
                        while enum_pos < L and 32 <= data[enum_pos] <= 126:
                            c = chr(data[enum_pos])
                            if c.isalnum() or c in [' ', '.', '-', '_']:
                                enum_value += c
                            enum_pos += 1
                        
                        enum_value = enum_value.strip()
                        if enum_value:
                            results.append((key, 'enum', f"{enum_type}.{enum_value}"))
                        else:
                            results.append((key, 'enum', f"{enum_type}"))
                        
                        next_pos = L
                        for next_marker in type_markers.keys():
                            found_next = data.find(next_marker, enum_pos)
                            if found_next != -1:
                                next_pos = min(next_pos, found_next)
                        pos = next_pos
                        found_marker = True
                        break
                
                elif marker_name == 'Objc':
                    obj_pos = pos + 4
                    
                    while obj_pos < L - 10:
                        if 97 <= data[obj_pos] <= 122:  # lowercase letter
                            class_name = ""
                            temp_pos = obj_pos
                            while temp_pos < L and (
                                (97 <= data[temp_pos] <= 122) or  # lowercase
                                (65 <= data[temp_pos] <= 90) or   # uppercase  
                                (48 <= data[temp_pos] <= 57) or   # numbers
                                data[temp_pos] in [95]            # underscore
                            ):
                                class_name += chr(data[temp_pos])
                                temp_pos += 1
                            
                            if len(class_name) > 3: 
                                results.append((key, 'Objc', class_name))
                                
                                pos = temp_pos
                                found_marker = True
                                break
                        
                        obj_pos += 1
                    
                    if not found_marker:
                        results.append((key, 'Objc', "no_class_found"))
                        pos = pos + 4
                        found_marker = True
                    break
                
                elif marker_name == 'VlLs':
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