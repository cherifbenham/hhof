# Legal Document Monitoring Platform

A comprehensive platform for monitoring and processing European Union legislative documents (EUR-LEX) and French Official Journal documents (JORF) with automated scraping, content extraction, and AI-powered analysis.

## 🎯 Overview

This platform automates the collection, processing, and analysis of legal documents from two primary sources:
- **EUR-LEX**: European Union legislative database
- **JORF**: French Official Journal (Journal Officiel de la République Française)

## 📊 Data Sources

### EUR-LEX (European Union Legislation)

**Source URLs:**
- L-Series: https://eur-lex.europa.eu/oj/daily-view/L-series/default.html
- C-Series: https://eur-lex.europa.eu/oj/daily-view/C-series/default.html

**Document Structure:**
```
id, date, url, typologie, ministere, titre, abstract, content, summary
```

**Document Types:**

#### L-Series (Legislative Acts)
- **II**: Non-legislative acts  
- **III**: Other acts  
- **Corrigenda**: Corrections

#### C-Series (Information & Notices)
- **II**: Information  
- **IV**: Notices  
- **V**: Announcements

**URL Pattern:**
```
https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_[DOCUMENT_ID]
```

**Example Document:**
```
2025/2269, 2025-11-13, https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202502269, 
"Implementing Regulation of the Commission", "", 
"Commission Regulation (EU) 2025/2269 of 12 November 2025 correcting Regulation (EU) 2022/1616 
as regards labelling of recycled plastic, the development of recycling technologies and the 
transfer of authorisations", [scraped_content]
```

### JORF (French Official Journal)

**Source:** https://www.legifrance.gouv.fr/jorf/

**Document Structure:**
```
id, date, url, typologie, ministere, titre, abstract, content
```

**Document Types:**
- **Avis**: Notices
- **Décret**: Decrees  
- **Arrêté**: Orders
- **Décision**: Decisions

**Example Document:**
```
1, [date], https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052250924, 
"arrêté", "MINISTÈRE DE LA CULTURE", 
"Arrêté du 15 septembre 2025 autorisant au titre de l'année 2025 l'ouverture d'un concours 
externe et d'un concours interne pour l'accès au corps de technicien d'art de classe normale 
du ministère de la culture - métiers du textile spécialité tapissier en garniture"
```

## 🔄 Processing Pipeline

### 1. Scraping
- **Frequency**: Daily automated scraping
- **Content Extraction**: Full text extraction from document URLs
- **Data Storage**: Structured format with metadata

### 2. AI-Powered Analysis

All inference processing uses configurable LLM parameters:
```
inferenceLLM(system_prompt, model, temperature, etc.)
```

#### Document Summarization
- **Input**: Full document content
- **Output**: Concise summary of key points
- **Language**: English (standardized)

#### Content Classification
- **Theme Classification**:
  ```python
  classPydantic = ["information", "obligation"]
  ```

- **Applicability Classification**:
  ```python
  classPydantic_2 = ["aeronautics", "automotive", "other"]
  ```

#### Keyword Extraction
- **Status**: To Be Determined (TBD)
- **Purpose**: Automated tagging for improved searchability

## 🛠️ Technical Architecture

### Data Flow
```
Source Documents → Scraping → Content Extraction → AI Analysis → Structured Database
```

### Key Components
1. **Web Scrapers**: Automated document collection
2. **Content Processors**: Text extraction and cleaning
3. **LLM Interface**: AI-powered analysis and classification
4. **Data Storage**: Structured document repository

## 📋 Data Schema

### Common Fields
| Field | Type | Description |
|-------|------|-------------|
| id | String | Unique document identifier |
| date | Date | Publication date |
| url | URL | Source document link |
| titre | String | Document title |
| abstract | String | Brief description |
| content | Text | Full document content |

### Source-Specific Fields

**EUR-LEX Additional Fields:**
- `typologie`: Document classification
- `ministere`: Ministry (typically empty for EU docs)
- `summary`: AI-generated summary

**JORF Additional Fields:**
- `typologie`: Document type (avis, décret, arrêté, décision)
- `ministere`: Responsible French ministry

## 🚀 Getting Started

### Prerequisites
- Python environment with LLM capabilities
- Web scraping dependencies
- Database for document storage

### Configuration
1. Configure LLM parameters for inference
2. Set up daily scraping schedule
3. Define classification categories as needed

## 📈 Future Enhancements

- [ ] Implement keyword extraction system
- [ ] Add multi-language support beyond English
- [ ] Expand classification categories
- [ ] Develop real-time monitoring capabilities
- [ ] Create user interface for document browsing

## 🔗 External Integrations

- **EUR-LEX API**: European legislation database
- **Legifrance**: French legal document repository
- **Email Notifications**: Automated updates via email

---

*This platform provides automated monitoring and analysis of legal documents to ensure compliance and awareness of regulatory changes across EU and French jurisdictions.*