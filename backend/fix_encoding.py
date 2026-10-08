import json

# Cargar el archivo actual
with open('style_catalog.json', 'r', encoding='utf-8') as f:
    catalog = json.load(f)

# Corregir los nombres que están mal
for mod in catalog['modifiers']:
    label = mod['label']
    text = mod['text']
    
    # Corregir Baterías
    if 'Bater' in label and 'protagonistas' in label:
        mod['label'] = 'Baterías protagonistas'
        mod['text'] = 'con las baterías como protagonistas'
    
    # Corregir Armonías
    if 'Armon' in label and 'coros' in label:
        mod['label'] = 'Armonías y coros'
        mod['text'] = 'con armonías y coros de fondo'

# Guardar
with open('style_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print('Archivo corregido')
