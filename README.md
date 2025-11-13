# EURLEX
plateforme EU législative

## INPUT

* https://eur-lex.europa.eu/oj/daily-view/L-series/default.html
id, date, url, typologie, ministere, titre, abstract, content, summary


2025/2269, 2025-11-13, https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202502269, " Implementing Regulation of the Commission", "Commission Regulation (EU) 2025/2269 of 12 November 2025 correcting Regulation (EU) 2022/1616 as regards labelling of recycled plastic, the development of recycling technologies and the transfer of authorisations", "", scraping text (https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202502269), URL = str("https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_") + ID

* ministere always empty in this case ""
* typologie :
- L : II Non-legislative acts,  III Other acts,  Corrigenda,
- C : II Information,  IV Notices,  V Announcements


* https://eur-lex.europa.eu/oj/daily-view/C-series/default.html
id, date, url, titre, abstract, content

* eml :

## Scraping

Run scraping script every day


## Inference
- Summary : inferenceLLM(system_prompt, model, temp, etc.)
- theme : classificationLLM(classPydantic, model)
applicability : classificationLLM(classPydantic_2, model)
- keywords : TBD
- Language = ENG

where classPydantic = list("information", "obligation")
classPydantic_2 = list("aeronotics", "automotive", "other")



## JORF

id, date, url, typlogie (avis, decret, arrete, decision), ministere, titre, abstract,content
1, ,  https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052250924, "decret", "MINISTERE DE LA CULTURE", "Arrêté du 15 septembre 2025 autorisant au titre de l'année 2025 l'ouverture d'un concours externe et d'un concours interne pour l'accès au corps de technicien d'art de classe normale du ministère de la culture - métiers du textile spécialité tapissier en garniture", "Arrêté du 15 septembre 2025 autorisant au titre de l'année 2025 l'ouverture d'un concours externe et d'un concours interne pour l'accès au corps de technicien d'art de classe normale du ministère de la culture - métiers du textile spécialité tapissier en garniture", scraping_txt(URL)
2,
3,
# hhof
# hhof
