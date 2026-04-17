# run this once in your project folder
from PIL import Image
img = Image.new('RGB', (32, 32), color='#87cefa')
img.save('static/favicon.ico')
