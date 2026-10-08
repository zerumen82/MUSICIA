#!/usr/bin/env python3
import json

# Cargar el backup
with open('style_catalog_backup.json', 'r', encoding='utf-8-sig') as f:
    catalog = json.load(f)

# Aplicar las nuevas cláusulas basadas en corpus real
new_clauses = {
    '4x4 (bombo a cada pulso)': 'a steady four-on-the-floor kick drum',
    'Doble bombo': 'aggressive double bass drumming',
    'A toda velocidad': 'a fast, energetic tempo',
    'Distorsionado': 'heavy distorted synths and guitars',
    'Baterías protagonistas': 'driving drums as the lead of the track',
    'Oscuro': 'a dark aggressive energy',
    'Épico': 'an epic, euphoric emotional lift throughout',
    'Melancólico': 'a melancholic, nostalgic emotional mood',
    'Luminoso': 'a bright, upbeat energy',
    'Voz susurrada': 'soft, whispered vocals',
    'Voz potente': 'powerful, commanding lead vocals',
    'Falsete': 'soaring falsetto vocals',
    'Voz gritada': 'raw, shouted vocals with grit',
    'Voz rapeada': 'rhythmic rapped verses',
    'Voz hablada': 'intimate, spoken passages',
    'Armonías y coros': 'rich vocal harmonies with ad-libs',
    'Tempo lento': 'a slow, laid-back tempo',
    'Tempo moderado': 'a steady mid-tempo feel',
    'Imparable (driving)': 'a relentless driving rhythm',
    'Pulso constante': 'a tight, steady pulse',
    'Himno': 'an anthemic, sing-along chorus',
    'Explosivo': 'explosive high-energy drops',
    'Con capas': 'layered, evolving textures',
    'Pegadizo': 'a catchy, memorable hook',
    'Riffs': 'punchy distorted guitar riffs',
    'Caja de ritmos': 'a raw, electronic drum-machine groove',
    'Contrabajo': 'a deep, upright bassline',
    'Sin voz': 'instrumental with no vocals',
}

# Aplicar
for mod in catalog['modifiers']:
    if mod['label'] in new_clauses:
        mod['clause'] = new_clauses[mod['label']]
        print(f"Actualizado: {mod['label']} -> {mod['clause']}")

# Guardar con codificación UTF-8
with open('style_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print('\nArchivo regenerado con clausulas nuevas y codificacion UTF-8')
