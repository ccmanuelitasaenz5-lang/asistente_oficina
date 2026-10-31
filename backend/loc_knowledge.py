import re
"""
Módulo de conocimiento jurídico y doctrinario de la Ley Orgánica de las Comunas (LOC).
Permite consultas y referencias a artículos y normas del autogobierno comunal.
"""

import logging
from typing import List, Dict

logger = logging.getLogger("loc_knowledge")

ARTICULOS_LOC = [
    {
        "articulo": 1,
        "titulo": "Objeto",
        "capitulo": "Disposiciones Generales",
        "texto": "La presente Ley tiene por objeto desarrollar y fortalecer el Poder Popular, estableciendo las normas que regulan la constitución, conformación, organización y funcionamiento de la Comuna, como entidad local donde los ciudadanos y ciudadanas en el ejercicio del Poder Popular ejercen el pleno derecho a la soberanía y desarrollan la edificación del estado comunal."
    },
    {
        "articulo": 4,
        "titulo": "Definición de Comuna",
        "capitulo": "Disposiciones Generales",
        "texto": "La Comuna es un espacio socialista que, como entidad local, es definida por la integración de comunidades vecinas con una memoria histórica compartida, rasgos culturales, usos y costumbres, que se reconocen en el territorio que ocupan y en las actividades productivas que le sirven de sustento, y sobre el cual ejercen los principios de soberanía y participación protagónica como expresión del Poder Popular."
    },
    {
        "articulo": 21,
        "titulo": "Definición del Parlamento Comunal",
        "capitulo": "Del Parlamento Comunal",
        "texto": "El Parlamento Comunal es la máxima instancia del autogobierno en la Comuna; y sus decisiones se expresan mediante la aprobación de normativas para la regulación de la vida social y comunitaria, coadyuvar con el orden público, la convivencia, la primacía del interés colectivo sobre el individual y la defensa de los derechos humanos."
    },
    {
        "articulo": 22,
        "titulo": "Integración del Parlamento Comunal",
        "capitulo": "Del Parlamento Comunal",
        "texto": "El Parlamento Comunal está integrado por: 1. Un vocero o vocera principal y su respectivo suplente, electo o electa por cada consejo comunal que integre la Comuna. 2. Tres voceros o voceras principales y sus respectivos suplentes, electos o electas por las organizaciones socioproductivas de la Comuna. 3. Un vocero o vocera principal y su respectivo suplente, en representación del Banco de la Comuna."
    },
    {
        "articulo": 28,
        "titulo": "Instancias de Gobierno Comunal",
        "capitulo": "De las Instancias de Gobierno",
        "texto": "El gobierno de la Comuna se ejerce a través de las siguientes instancias: 1. El Parlamento Comunal. 2. El Consejo Ejecutivo. 3. La Comisión Electoral Permanente Comunal. 4. El Consejo de Contraloría Comunal. 5. El Banco de la Comuna. 6. El Consejo de Justicia de Paz Comunal."
    },
    {
        "articulo": 30,
        "titulo": "Comisiones de Gestión Comunal",
        "capitulo": "De las Comisiones de Gestión",
        "texto": "Las Comisiones de Gestión Comunal son las encargadas de articular y coordinar con los comités de trabajo de los consejos comunales las políticas, planes y proyectos relacionados con las distintas áreas de interés comunitario, tales como salud, educación, hábitat y vivienda, economía comunal, seguridad y defensa integral, entre otras."
    },
    {
        "articulo": 36,
        "titulo": "Comisión Electoral Permanente",
        "capitulo": "De la Comisión Electoral",
        "texto": "La Comisión Electoral Permanente es la instancia encargada de organizar, coordinar y supervisar los procesos de elección, revocatoria de vocerías y consultas populares que se realicen en el ámbito territorial de la Comuna, en coordinación con los órganos correspondientes."
    },
    {
        "articulo": 37,
        "titulo": "Consejo de Contraloría Comunal",
        "capitulo": "Del Consejo de Contraloría",
        "texto": "El Consejo de Contraloría Comunal es la instancia encargada de la vigilancia, control, seguimiento, supervisión y evaluación social sobre los planes, programas, proyectos y el uso de los recursos de la Comuna, así como sobre la conducta de los voceros y voceras en el ejercicio de sus funciones."
    },
    {
        "articulo": 38,
        "titulo": "Banco de la Comuna",
        "capitulo": "Del Banco de la Comuna",
        "texto": "El Banco de la Comuna es la organización económico-financiera de carácter social, encargada de la gestión, administración, captación y colocación de los recursos financieros y no financieros, retornables y no retornables de la Comuna, para impulsar el desarrollo socioeconómico y los proyectos socioproductivos."
    },
    {
        "articulo": 41,
        "titulo": "Gaceta Comunal",
        "capitulo": "De la Gaceta Comunal",
        "texto": "Las decisiones, leyes comunales, acuerdos y resoluciones del Parlamento Comunal se publicarán en la Gaceta Comunal, órgano oficial de difusión de la Comuna, adquiriendo fuerza vinculante y obligatoriedad en el territorio comunal a partir de su publicación."
    },
    {
        "articulo": 47,
        "titulo": "Agenda Concreta de Acción y Plan Comunal de Desarrollo",
        "capitulo": "De los Planes y Proyectos",
        "texto": "El Plan de Desarrollo Comunal y la Agenda Concreta de Acción (ACA) constituyen los instrumentos de planificación participativa donde se plasman las necesidades prioritarias, las potencialidades y las metas socioproductivas de la Comuna, aprobadas en asamblea de ciudadanas y ciudadanos."
    },
    {
        "articulo": 52,
        "titulo": "Rendición de Cuentas",
        "capitulo": "De la Rendición de Cuentas",
        "texto": "Los voceros y voceras de todas las instancias de gobierno de la Comuna están en la obligación de rendir cuentas públicas de su gestión de manera anual o cuando les sea requerido, ante el Parlamento Comunal y la asamblea de ciudadanas y ciudadanos, presentando el balance financiero, físico y social de los recursos administrados."
    },
    {
        "articulo": 54,
        "titulo": "Consejo de Justicia de Paz Comunal",
        "capitulo": "De la Justicia de Paz",
        "texto": "El Consejo de Justicia de Paz Comunal es la instancia encargada de promover la convivencia pacífica, la conciliación y la resolución armónica de conflictos comunitarios y vecinales dentro del territorio de la Comuna, con apego a las leyes y a la equidad."
    }
]


def buscar_articulos_loc(query: str) -> List[Dict]:
    """Busca artículos relevantes en la Ley Orgánica de las Comunas."""
    q = query.lower()
    resultados = []

    # Búsqueda robusta por número de artículo usando regex
    m = re.search(r'\b(?:art[íi]culo|art\.?|n[°º]|num|número)\s*(\d+)\b', q)
    art_num_detectado = int(m.group(1)) if m else None

    for art in ARTICULOS_LOC:
        if art_num_detectado and art["articulo"] == art_num_detectado:
            return [{
                "fuente": "loc_ley",
                "tipo_doc": f"LOC — Artículo {art['articulo']}",
                "numero": art["articulo"],
                "titulo": art["titulo"],
                "capitulo": art["capitulo"],
                "texto": art["texto"],
                "resumen": f"Art. {art['articulo']} LOC ({art['titulo']}): {art['texto'][:160]}...",
                "score": 0.99
            }]

    # Búsqueda por palabras clave temáticas
    for art in ARTICULOS_LOC:
        texto_completo = f"{art['titulo']} {art['capitulo']} {art['texto']}".lower()
        palabras_q = [p for p in q.split() if len(p) > 3]
        coincidencias = sum(1 for p in palabras_q if p in texto_completo)

        if coincidencias > 0:
            score = coincidencias / max(len(palabras_q), 1)
            resultados.append({
                "fuente": "loc_ley",
                "tipo_doc": f"LOC — Artículo {art['articulo']}",
                "numero": art["articulo"],
                "titulo": art["titulo"],
                "capitulo": art["capitulo"],
                "texto": art["texto"],
                "resumen": f"Art. {art['articulo']} LOC ({art['titulo']}): {art['texto'][:150]}...",
                "score": score
            })

    resultados.sort(key=lambda x: x["score"], reverse=True)
    return resultados[:5]

