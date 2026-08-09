"""Run benchmark on first 60 BLR images"""
import sys
sys.path.insert(0, 'C:/Users/dhruv/PycharmProjects/A.R.I.A')

from scripts.run_benchmark import main
import sys
sys.argv = ['run_benchmark.py', '--limit', '60']
main()