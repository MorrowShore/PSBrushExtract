#!/usr/bin/env python3
# Author: Morrow Shore
# License: AGPLv3
# Contact: inquiry@morrowshore.com

import struct
import os
import sys
from PIL import Image
import io


class AbrExtractor:
    def __init__(self, abr_file_path):
        self.abr_file_path = abr_file_path
        self.brushes = []

    def read_char(self, f):
        data = f.read(1)
        if len(data) != 1:
            raise EOFError("Unexpected end of file")
        return struct.unpack('>B', data)[0]

    def read_short(self, f):
        data = f.read(2)
        if len(data) != 2:
            raise EOFError("Unexpected end of file")
        return struct.unpack('>h', data)[0]

    def read_long(self, f):
        data = f.read(4)
        if len(data) != 4:
            raise EOFError("Unexpected end of file")
        return struct.unpack('>l', data)[0]

    def read_ucs2_text(self, f):
        length = self.read_long(f) * 2
        if length <= 0:
            return ""
        
        data = f.read(length)
        if len(data) != length:
            raise EOFError("Unexpected end of file")
        
        try:
            return data.decode('utf-16be').rstrip('\x00')
        except UnicodeDecodeError:
            return "Unknown"

    def abr_rle_decode(self, f, height, width):
        scanline_lengths = []
        for i in range(height):
            scanline_lengths.append(self.read_short(f))

        buffer = bytearray(height * width)
        data_pos = 0

        for i in range(height):
            j = 0
            while j < scanline_lengths[i]:
                n = self.read_char(f)
                j += 1

                if n >= 128:
                    n -= 256

                if n < 0:
                    if n == -128:
                        continue
                    
                    n = -n + 1
                    ch = self.read_char(f)
                    j += 1

                    for c in range(n):
                        if data_pos < len(buffer):
                            buffer[data_pos] = ch
                            data_pos += 1
                else:
                    for c in range(n + 1):
                        ch = self.read_char(f)
                        j += 1
                        if data_pos < len(buffer):
                            buffer[data_pos] = ch
                            data_pos += 1

        return bytes(buffer)

    def load_abr_v12(self, f, version, count):
        brushes = []
        
        for i in range(count):
            try:
                brush_type = self.read_short(f)
                brush_size = self.read_long(f)
                
                print(f"Brush {i+1}: type={brush_type}, size={brush_size}")
                
                if brush_type == 1:
                    print(f"  Skipping computed brush")
                    f.seek(brush_size, 1)
                    continue
                
                elif brush_type == 2:
                    misc = self.read_long(f)
                    spacing = self.read_short(f)
                    
                    sample_name = ""
                    if version == 2:
                        sample_name = self.read_ucs2_text(f)
                    
                    antialiasing = self.read_char(f)
                    
                    bounds = []
                    for j in range(4):
                        bounds.append(self.read_short(f))
                    
                    bounds_long = []
                    for j in range(4):
                        bounds_long.append(self.read_long(f))
                    
                    depth = self.read_short(f)
                    
                    height = bounds_long[2] - bounds_long[0] 
                    width = bounds_long[3] - bounds_long[1]  
                    
                    print(f"  Sampled brush: {width}x{height}, depth={depth}, spacing={spacing}")
                    if sample_name:
                        print(f"  Name: {sample_name}")
                    
                    if height > 16384:
                        print(f"  Skipping wide brush (height > 16384)")
                        continue
                    
                    compress = self.read_char(f)
                    
                    if not compress:
                        data_size = width * height * (depth // 8)
                        brush_data = f.read(data_size)
                        if len(brush_data) != data_size:
                            print(f"  Warning: Expected {data_size} bytes, got {len(brush_data)}")
                            continue
                    else:
                        brush_data = self.abr_rle_decode(f, height, width)
                    
                    brush_info = {
                        'index': i + 1,
                        'name': sample_name or f"brush_{i+1:03d}",
                        'width': width,
                        'height': height,
                        'depth': depth,
                        'spacing': spacing,
                        'data': brush_data
                    }
                    brushes.append(brush_info)
                
                else:
                    print(f"  Skipping unknown brush type {brush_type}")
                    f.seek(brush_size, 1)
                    
            except Exception as e:
                print(f"Error processing brush {i+1}: {e}")
                break
        
        return brushes

    def reach_8bim_section(self, f, section_name):
        while True:
            try:
                tag = f.read(4)
                if len(tag) != 4 or tag != b'8BIM':
                    return False
                
                tagname = f.read(4)
                if len(tagname) != 4:
                    return False
                
                if tagname == section_name.encode('ascii'):
                    return True
                
                section_size = self.read_long(f)
                f.seek(section_size, 1)
                
            except (EOFError, struct.error):
                return False

    def load_abr_v6(self, f, subversion):
        brushes = []
        
        if not self.reach_8bim_section(f, 'samp'):
            print("Could not find 'samp' section")
            return brushes
        
        sample_section_size = self.read_long(f)
        sample_section_end = f.tell() + sample_section_size
        
        index = 1
        while f.tell() < sample_section_end:
            try:
                brush_size = self.read_long(f)
                brush_end = brush_size
                

                while brush_end % 4 != 0:
                    brush_end += 1
                
                next_brush = f.tell() + brush_end
                

                if subversion == 1:
                    f.seek(47, 1)
                else:
                    f.seek(301, 1)
                
                top = self.read_long(f)
                left = self.read_long(f)
                bottom = self.read_long(f)
                right = self.read_long(f)
                depth = self.read_short(f)
                compress = self.read_char(f)
                
                width = right - left
                height = bottom - top
                
                print(f"Brush {index}: {width}x{height}, depth={depth}, compressed={bool(compress)}")
                
                if width <= 0 or height <= 0:
                    print(f"  Invalid dimensions, skipping")
                    f.seek(next_brush)
                    continue
                
                if not compress:
                    data_size = width * height * (depth // 8)
                    brush_data = f.read(data_size)
                    if len(brush_data) != data_size:
                        print(f"  Warning: Expected {data_size} bytes, got {len(brush_data)}")
                        f.seek(next_brush)
                        continue
                else:
                    brush_data = self.abr_rle_decode(f, height, width)
                
                brush_info = {
                    'index': index,
                    'name': f"brush_{index:03d}",
                    'width': width,
                    'height': height,
                    'depth': depth,
                    'spacing': 25, 
                    'data': brush_data
                }
                brushes.append(brush_info)
                
                f.seek(next_brush)
                index += 1
                
            except Exception as e:
                print(f"Error processing brush {index}: {e}")
                break
        
        return brushes

    def load_abr_v10(self, f, subversion):
        """Load ABR version 10 (CS6+)"""
        brushes = []
        
        if not self.reach_8bim_section(f, 'samp'):
            print("Could not find 'samp' section")
            return brushes
        
        sample_section_size = self.read_long(f)
        sample_section_end = f.tell() + sample_section_size
        
        index = 1
        while f.tell() < sample_section_end:
            try:
                brush_size = self.read_long(f)
                brush_end = brush_size
                
                while brush_end % 4 != 0:
                    brush_end += 1
                
                next_brush = f.tell() + brush_end
                
                if subversion == 1:
                    f.seek(47, 1)  
                elif subversion == 2:
                    f.seek(301, 1)  
                else:
                    start_pos = f.tell()
                    found = False
                    
                    for offset in range(0, min(500, brush_size), 4):
                        f.seek(start_pos + offset)
                        try:
                            top = self.read_long(f)
                            left = self.read_long(f)
                            bottom = self.read_long(f)
                            right = self.read_long(f)
                            depth = self.read_short(f)
                            
                            width = right - left
                            height = bottom - top
                            
                            if (width > 0 and height > 0 and width < 10000 and height < 10000 and 
                                depth in [1, 8, 16, 24, 32] and top >= 0 and left >= 0):
                                print(f"  Found brush data at offset {offset}")
                                found = True
                                break
                        except:
                            continue
                    
                    if not found:
                        print(f"  Could not locate brush data for brush {index}")
                        f.seek(next_brush)
                        continue
                
                try:
                    top = self.read_long(f)
                    left = self.read_long(f)
                    bottom = self.read_long(f)
                    right = self.read_long(f)
                    depth = self.read_short(f)
                    compress = self.read_char(f)
                except:
                    print(f"  Error reading brush parameters for brush {index}")
                    f.seek(next_brush)
                    continue
                
                width = right - left
                height = bottom - top
                
                print(f"Brush {index}: {width}x{height}, depth={depth}, compressed={bool(compress)}")
                
                if width <= 0 or height <= 0:
                    print(f"  Invalid dimensions, skipping")
                    f.seek(next_brush)
                    continue
                
                try:
                    if not compress:
                        data_size = width * height * (depth // 8)
                        brush_data = f.read(data_size)
                        if len(brush_data) != data_size:
                            print(f"  Warning: Expected {data_size} bytes, got {len(brush_data)}")
                            f.seek(next_brush)
                            continue
                    else:
                        brush_data = self.abr_rle_decode(f, height, width)
                    
                    brush_info = {
                        'index': index,
                        'name': f"brush_{index:03d}",
                        'width': width,
                        'height': height,
                        'depth': depth,
                        'spacing': 25, 
                        'data': brush_data
                    }
                    brushes.append(brush_info)
                    
                except Exception as e:
                    print(f"  Error reading brush data for brush {index}: {e}")
                
                f.seek(next_brush)
                index += 1
                
            except Exception as e:
                print(f"Error processing brush {index}: {e}")
                break
        
        return brushes

    def extract_brushes(self):
        with open(self.abr_file_path, 'rb') as f:
            try:
                version = self.read_short(f)
                count = self.read_short(f)
                
                print(f"ABR file version: {version}, count/subversion: {count}")
                
                if version in [1, 2]:
                    self.brushes = self.load_abr_v12(f, version, count)
                elif version == 6:
                    if count in [1, 2]:
                        self.brushes = self.load_abr_v6(f, count)
                    else:
                        print(f"Unsupported ABR v6 subversion: {count}")
                        return False
                elif version == 10:
                    self.brushes = self.load_abr_v10(f, count)
                else:
                    print(f"Unsupported ABR version: {version}")
                    return False
                
                print(f"Successfully extracted {len(self.brushes)} brushes")
                return True
                
            except Exception as e:
                print(f"Error reading ABR file: {e}")
                return False

    def save_brush_images(self, output_dir=None):
        if not self.brushes:
            print("No brushes to save")
            return
        
        if output_dir is None:
            base_name = os.path.splitext(os.path.basename(self.abr_file_path))[0]
            output_dir = f"{base_name}_brushtips"
        
        os.makedirs(output_dir, exist_ok=True)
        
        for brush in self.brushes:
            try:
                width = brush['width']
                height = brush['height']
                depth = brush['depth']
                data = brush['data']
                
                if depth == 8:
                    if len(data) != width * height:
                        print(f"Warning: Data size mismatch for brush {brush['index']}")
                        continue
                    
                    img = Image.frombytes('L', (width, height), data)
                elif depth == 32:
                    if len(data) != width * height * 4:
                        print(f"Warning: Data size mismatch for brush {brush['index']}")
                        continue
                    
                    pixels = []
                    alpha = []
                    for i in range(0, len(data), 4):
                        pixels.extend([data[i], data[i+1], data[i+2]])
                        alpha.append(data[i+3]) 
                    
                    rgb_img = Image.frombytes('RGB', (width, height), bytes(pixels))
                    alpha_img = Image.frombytes('L', (width, height), bytes(alpha))
                    img = Image.merge('RGBA', (rgb_img.split()[0], rgb_img.split()[1], rgb_img.split()[2], alpha_img))
                else:
                    print(f"Unsupported bit depth {depth} for brush {brush['index']}")
                    continue
                
                filename = f"{brush['name']}_{brush['index']:03d}.png"
                filepath = os.path.join(output_dir, filename)
                img.save(filepath)
                print(f"Saved: {filepath}")
                
            except Exception as e:
                print(f"Error saving brush {brush['index']}: {e}")
        
        print(f"Brushes saved to: {output_dir}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python psbrushtipextract.py <path_to_abr_file>")
        sys.exit(1)
    
    abr_file = sys.argv[1]
    
    if not os.path.exists(abr_file):
        print(f"File not found: {abr_file}")
        sys.exit(1)
    
    extractor = AbrExtractor(abr_file)
    
    if extractor.extract_brushes():
        extractor.save_brush_images()
    else:
        print("Failed to extract brushes")
        sys.exit(1)


if __name__ == "__main__":
    main()