import fitz
d = fitz.open('poster2.pdf')
pg = d[0]
print('page size (pt):', pg.rect)
# full page
pg.get_pixmap(dpi=40).save('preview_full3.png')
# middle column close-up
clip = fitz.Rect(630, 270, 1750, 2500)
pg.get_pixmap(dpi=70, clip=clip).save('preview_mid3.png')
# left + right columns (check for overflow)
pg.get_pixmap(dpi=60, clip=fitz.Rect(20, 560, 700, 3000)).save('preview_left3.png')
pg.get_pixmap(dpi=60, clip=fitz.Rect(1680, 560, 2370, 3000)).save('preview_right3.png')
print('previews written')
