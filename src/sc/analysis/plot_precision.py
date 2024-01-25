'''
Created on Jan 25, 2024

@author: immanueltrummer
'''
import argparse
import json


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('inpath', type=str, help='Path to input file')
    args = parser.parse_args()
    
    with open(args.inpath) as file:
        data = json.load(file)
    
    correct_original = len([d for d in data if d['original']])
    correct_compressed = len([d for d in data if d['compressed']])
    
    print(f'#Correct Original: {correct_original}')
    print(f'#Correct Compressed: {correct_compressed}')