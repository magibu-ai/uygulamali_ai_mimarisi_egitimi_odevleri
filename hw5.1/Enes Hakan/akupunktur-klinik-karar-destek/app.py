"""Streamlit arayuzu."""

import os
import re
from pathlib import Path

import streamlit as st

import chat

st.set_page_config(page_title="Akupunktur Karar Destek", page_icon="🩺")
st.title("Akupunktur Klinik Karar Destek")
st.caption("Kesin tanı değildir; son karar hekimindir.")

with st.form("case"):
    complaint = st.text_input("Ana şikâyet ve süre *")
    tongue = st.text_input("Dil bulgusu")
    pulse = st.text_input("Nabız bulgusu")
    other = st.text_area("Diğer önemli bulgular / mevcut tanılar")
    note = st.text_area("Ek not")
    submitted = st.form_submit_button("Vakayı değerlendir", type="primary")

if submitted:
    if not complaint.strip():
        st.error("Ana şikâyet ve süre zorunludur.")
    elif not os.getenv("ACUPUNCTURE_PDF"):
        st.error("ACUPUNCTURE_PDF ayarlanmamış. Uygulamayı README'deki komutla başlatın.")
    else:
        case = "\n".join((
            f"Ana şikâyet ve süre: {complaint}", f"Dil bulgusu: {tongue or 'belirtilmedi'}",
            f"Nabız bulgusu: {pulse or 'belirtilmedi'}",
            f"Diğer önemli bulgular / mevcut tanılar: {other or 'belirtilmedi'}",
            f"Ek not: {note or 'belirtilmedi'}",
        ))
        with st.spinner("Kitap taranıyor ve kaynaklar doğrulanıyor…"):
            answer = chat.answer(case)
        st.markdown(answer)
        images = dict.fromkeys(re.findall(r"/[^`\s]+\.png", answer))
        for image in images:
            if Path(image).is_file():
                st.image(image, caption=Path(image).name)
