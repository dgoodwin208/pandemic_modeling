import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Volume2, VolumeX, Globe, Mic } from 'lucide-react';

// =============================================================================
// Country → Multi-Language Audio Data
// Each country has a `languages` array ordered by national importance.
// First click plays languages[0], click again cycles to next, loops back.
// =============================================================================

const COUNTRY_DATA = {
  // ── Arabic-speaking ──────────────────────────────────────────────────────
  DZA: { flag: '🇩🇿', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في الجزائر',
      greetingEnglish: 'Hello! Welcome to Algeria.',
      audioFile: '/audio/algeria_arabic.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue en Algérie.',
      greetingEnglish: 'Hello! Welcome to Algeria.',
      audioFile: '/audio/algeria_french.mp3' },
  ]},
  TCD: { flag: '🇹🇩', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في تشاد',
      greetingEnglish: 'Hello! Welcome to Chad.',
      audioFile: '/audio/chad_arabic.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Tchad.',
      greetingEnglish: 'Hello! Welcome to Chad.',
      audioFile: '/audio/chad_french.mp3' },
  ]},
  DJI: { flag: '🇩🇯', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في جيبوتي',
      greetingEnglish: 'Hello! Welcome to Djibouti.',
      audioFile: '/audio/djibouti_arabic.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue à Djibouti.',
      greetingEnglish: 'Hello! Welcome to Djibouti.',
      audioFile: '/audio/djibouti_french.mp3' },
  ]},
  EGY: { flag: '🇪🇬', agentIntro: 'If this were an AI agent serving Egypt, this is how it might greet you — in the local language, with warmth and authority.', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في مصر',
      greetingEnglish: 'Hello! Welcome to Egypt.',
      audioFile: '/audio/egypt_arabic.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Egypt.',
      greetingEnglish: 'Hello! Welcome to Egypt.',
      audioFile: '/audio/egypt_english.mp3' },
  ]},
  ERI: { flag: '🇪🇷', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في إريتريا',
      greetingEnglish: 'Hello! Welcome to Eritrea.',
      audioFile: '/audio/eritrea_arabic.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Eritrea.',
      greetingEnglish: 'Hello! Welcome to Eritrea.',
      audioFile: '/audio/eritrea_english.mp3' },
  ]},
  LBY: { flag: '🇱🇾', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في ليبيا',
      greetingEnglish: 'Hello! Welcome to Libya.',
      audioFile: '/audio/libya_arabic.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Libya.',
      greetingEnglish: 'Hello! Welcome to Libya.',
      audioFile: '/audio/libya_english.mp3' },
  ]},
  MRT: { flag: '🇲🇷', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في موريتانيا',
      greetingEnglish: 'Hello! Welcome to Mauritania.',
      audioFile: '/audio/mauritania_arabic.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue en Mauritanie.',
      greetingEnglish: 'Hello! Welcome to Mauritania.',
      audioFile: '/audio/mauritania_french.mp3' },
  ]},
  MAR: { flag: '🇲🇦', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في المغرب',
      greetingEnglish: 'Hello! Welcome to Morocco.',
      audioFile: '/audio/morocco_arabic.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Maroc.',
      greetingEnglish: 'Hello! Welcome to Morocco.',
      audioFile: '/audio/morocco_french.mp3' },
  ]},
  SOM: { flag: '🇸🇴', languages: [
    { language: 'Somali', languageNative: 'Soomaali',
      greeting: 'Salaan! Ku soo dhawoow Soomaaliya.',
      greetingEnglish: 'Hello! Welcome to Somalia.',
      audioFile: '/audio/somalia_somali.mp3' },
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في الصومال',
      greetingEnglish: 'Hello! Welcome to Somalia.',
      audioFile: '/audio/somalia_arabic.mp3' },
  ]},
  SDN: { flag: '🇸🇩', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في السودان',
      greetingEnglish: 'Hello! Welcome to Sudan.',
      audioFile: '/audio/sudan_arabic.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Sudan.',
      greetingEnglish: 'Hello! Welcome to Sudan.',
      audioFile: '/audio/sudan_english.mp3' },
  ]},
  TUN: { flag: '🇹🇳', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في تونس',
      greetingEnglish: 'Hello! Welcome to Tunisia.',
      audioFile: '/audio/tunisia_arabic.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue en Tunisie.',
      greetingEnglish: 'Hello! Welcome to Tunisia.',
      audioFile: '/audio/tunisia_french.mp3' },
  ]},
  ESH: { flag: '🇪🇭', languages: [
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في الصحراء الغربية',
      greetingEnglish: 'Hello! Welcome to Western Sahara.',
      audioFile: '/audio/western_sahara_arabic.mp3' },
  ]},

  // ── French-speaking ──────────────────────────────────────────────────────
  BEN: { flag: '🇧🇯', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Bénin.',
      greetingEnglish: 'Hello! Welcome to Benin.',
      audioFile: '/audio/benin_french.mp3' },
    { language: 'Yoruba', languageNative: 'Yorùbá',
      greeting: 'Ẹ kú àbọ̀! Ẹ kú ilé Benin.',
      greetingEnglish: 'Hello! Welcome to Benin.',
      audioFile: '/audio/benin_yoruba.mp3' },
  ]},
  BFA: { flag: '🇧🇫', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Burkina Faso.',
      greetingEnglish: 'Hello! Welcome to Burkina Faso.',
      audioFile: '/audio/burkina_faso_french.mp3' },
  ]},
  BDI: { flag: '🇧🇮', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Burundi.',
      greetingEnglish: 'Hello! Welcome to Burundi.',
      audioFile: '/audio/burundi_french.mp3' },
    { language: 'Kinyarwanda', languageNative: 'Ikinyarwanda',
      greeting: 'Muraho! Murakaza neza mu Burundi.',
      greetingEnglish: 'Hello! Welcome to Burundi.',
      audioFile: '/audio/burundi_kinyarwanda.mp3' },
  ]},
  CMR: { flag: '🇨🇲', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Cameroun.',
      greetingEnglish: 'Hello! Welcome to Cameroon.',
      audioFile: '/audio/cameroon_french.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Cameroon.',
      greetingEnglish: 'Hello! Welcome to Cameroon.',
      audioFile: '/audio/cameroon_english.mp3' },
  ]},
  CAF: { flag: '🇨🇫', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue en République centrafricaine.',
      greetingEnglish: 'Hello! Welcome to the Central African Republic.',
      audioFile: '/audio/central_african_republic_french.mp3' },
  ]},
  COM: { flag: '🇰🇲', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue aux Comores.',
      greetingEnglish: 'Hello! Welcome to Comoros.',
      audioFile: '/audio/comoros_french.mp3' },
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في جزر القمر',
      greetingEnglish: 'Hello! Welcome to Comoros.',
      audioFile: '/audio/comoros_arabic.mp3' },
  ]},
  COD: { flag: '🇨🇩', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue en République démocratique du Congo.',
      greetingEnglish: 'Hello! Welcome to the Democratic Republic of the Congo.',
      audioFile: '/audio/drc_french.mp3' },
    { language: 'Lingala', languageNative: 'Lingála',
      greeting: 'Mbote! Boyei malamu na République démocratique ya Congo.',
      greetingEnglish: 'Hello! Welcome to the Democratic Republic of the Congo.',
      audioFile: '/audio/drc_lingala.mp3' },
    { language: 'Swahili', languageNative: 'Kiswahili',
      greeting: 'Habari! Karibu Jamhuri ya Kidemokrasia ya Kongo.',
      greetingEnglish: 'Hello! Welcome to the Democratic Republic of the Congo.',
      audioFile: '/audio/drc_swahili.mp3' },
  ]},
  COG: { flag: '🇨🇬', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Congo.',
      greetingEnglish: 'Hello! Welcome to the Republic of the Congo.',
      audioFile: '/audio/congo_french.mp3' },
    { language: 'Lingala', languageNative: 'Lingála',
      greeting: 'Mbote! Boyei malamu na Congo.',
      greetingEnglish: 'Hello! Welcome to the Republic of the Congo.',
      audioFile: '/audio/congo_lingala.mp3' },
  ]},
  CIV: { flag: '🇨🇮', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: "Bonjour ! Bienvenue en Côte d'Ivoire.",
      greetingEnglish: 'Hello! Welcome to Ivory Coast.',
      audioFile: '/audio/ivory_coast_french.mp3' },
  ]},
  GAB: { flag: '🇬🇦', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Gabon.',
      greetingEnglish: 'Hello! Welcome to Gabon.',
      audioFile: '/audio/gabon_french.mp3' },
  ]},
  GIN: { flag: '🇬🇳', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue en Guinée.',
      greetingEnglish: 'Hello! Welcome to Guinea.',
      audioFile: '/audio/guinea_french.mp3' },
  ]},
  MDG: { flag: '🇲🇬', languages: [
    { language: 'Malagasy', languageNative: 'Malagasy',
      greeting: 'Manao ahoana! Tongasoa eto Madagasikara.',
      greetingEnglish: 'Hello! Welcome to Madagascar.',
      audioFile: '/audio/madagascar_malagasy.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue à Madagascar.',
      greetingEnglish: 'Hello! Welcome to Madagascar.',
      audioFile: '/audio/madagascar_french.mp3' },
  ]},
  MLI: { flag: '🇲🇱', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Mali.',
      greetingEnglish: 'Hello! Welcome to Mali.',
      audioFile: '/audio/mali_french.mp3' },
  ]},
  NER: { flag: '🇳🇪', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Niger.',
      greetingEnglish: 'Hello! Welcome to Niger.',
      audioFile: '/audio/niger_french.mp3' },
    { language: 'Hausa', languageNative: 'Hausa',
      greeting: 'Sannu! Barka da zuwa Niger.',
      greetingEnglish: 'Hello! Welcome to Niger.',
      audioFile: '/audio/niger_hausa.mp3' },
  ]},
  RWA: { flag: '🇷🇼', languages: [
    { language: 'Kinyarwanda', languageNative: 'Ikinyarwanda',
      greeting: 'Muraho! Murakaza neza mu Rwanda.',
      greetingEnglish: 'Hello! Welcome to Rwanda.',
      audioFile: '/audio/rwanda_kinyarwanda.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Rwanda.',
      greetingEnglish: 'Hello! Welcome to Rwanda.',
      audioFile: '/audio/rwanda_french.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Rwanda.',
      greetingEnglish: 'Hello! Welcome to Rwanda.',
      audioFile: '/audio/rwanda_english.mp3' },
  ]},
  SEN: { flag: '🇸🇳', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Sénégal.',
      greetingEnglish: 'Hello! Welcome to Senegal.',
      audioFile: '/audio/senegal_french.mp3' },
  ]},
  STP: { flag: '🇸🇹', languages: [
    { language: 'Portuguese', languageNative: 'Português',
      greeting: 'Olá! Bem-vindo a São Tomé e Príncipe.',
      greetingEnglish: 'Hello! Welcome to São Tomé and Príncipe.',
      audioFile: '/audio/sao_tome_portuguese.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue à São Tomé-et-Príncipe.',
      greetingEnglish: 'Hello! Welcome to São Tomé and Príncipe.',
      audioFile: '/audio/sao_tome_french.mp3' },
  ]},
  TGO: { flag: '🇹🇬', languages: [
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue au Togo.',
      greetingEnglish: 'Hello! Welcome to Togo.',
      audioFile: '/audio/togo_french.mp3' },
  ]},

  // ── English-speaking ─────────────────────────────────────────────────────
  BWA: { flag: '🇧🇼', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Botswana.',
      greetingEnglish: 'Hello! Welcome to Botswana.',
      audioFile: '/audio/botswana_english.mp3' },
    { language: 'Setswana', languageNative: 'Setswana',
      greeting: 'Dumela! O amogetswe mo Botswana.',
      greetingEnglish: 'Hello! Welcome to Botswana.',
      audioFile: '/audio/botswana_setswana.mp3' },
  ]},
  GMB: { flag: '🇬🇲', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to The Gambia.',
      greetingEnglish: 'Hello! Welcome to The Gambia.',
      audioFile: '/audio/gambia_english.mp3' },
  ]},
  GHA: { flag: '🇬🇭', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Ghana.',
      greetingEnglish: 'Hello! Welcome to Ghana.',
      audioFile: '/audio/ghana_english.mp3' },
  ]},
  KEN: { flag: '🇰🇪', languages: [
    { language: 'Swahili', languageNative: 'Kiswahili',
      greeting: 'Habari! Karibu Kenya. Mimi ni msaidizi wako wa akili bandia.',
      greetingEnglish: 'Hello! Welcome to Kenya.',
      audioFile: '/audio/kenya_swahili.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Kenya. Karibu sana!',
      greetingEnglish: 'Hello! Welcome to Kenya.',
      audioFile: '/audio/kenya_english.mp3' },
  ]},
  LSO: { flag: '🇱🇸', languages: [
    { language: 'Sesotho', languageNative: 'Sesotho',
      greeting: 'Lumela! Rea u amohela Lesotho.',
      greetingEnglish: 'Hello! Welcome to Lesotho.',
      audioFile: '/audio/lesotho_sesotho.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Lesotho.',
      greetingEnglish: 'Hello! Welcome to Lesotho.',
      audioFile: '/audio/lesotho_english.mp3' },
  ]},
  LBR: { flag: '🇱🇷', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Liberia.',
      greetingEnglish: 'Hello! Welcome to Liberia.',
      audioFile: '/audio/liberia_english.mp3' },
  ]},
  MWI: { flag: '🇲🇼', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Malawi, the warm heart of Africa.',
      greetingEnglish: 'Hello! Welcome to Malawi, the warm heart of Africa.',
      audioFile: '/audio/malawi_english.mp3' },
    { language: 'Chichewa', languageNative: 'Chicheŵa',
      greeting: 'Moni! Takulandirani ku Malawi, mtima wofunda wa Africa.',
      greetingEnglish: 'Hello! Welcome to Malawi, the warm heart of Africa.',
      audioFile: '/audio/malawi_chichewa.mp3' },
  ]},
  MUS: { flag: '🇲🇺', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Mauritius.',
      greetingEnglish: 'Hello! Welcome to Mauritius.',
      audioFile: '/audio/mauritius_english.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue à Maurice.',
      greetingEnglish: 'Hello! Welcome to Mauritius.',
      audioFile: '/audio/mauritius_french.mp3' },
  ]},
  NGA: { flag: '🇳🇬', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Nigeria.',
      greetingEnglish: 'Hello! Welcome to Nigeria.',
      audioFile: '/audio/nigeria_english.mp3' },
    { language: 'Yoruba', languageNative: 'Yorùbá',
      greeting: 'Ẹ kú àbọ̀! Ẹ kú ilé Nigeria.',
      greetingEnglish: 'Hello! Welcome to Nigeria.',
      audioFile: '/audio/nigeria_yoruba.mp3' },
    { language: 'Hausa', languageNative: 'Hausa',
      greeting: 'Sannu! Barka da zuwa Nigeria.',
      greetingEnglish: 'Hello! Welcome to Nigeria.',
      audioFile: '/audio/nigeria_hausa.mp3' },
  ]},
  SYC: { flag: '🇸🇨', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Seychelles.',
      greetingEnglish: 'Hello! Welcome to Seychelles.',
      audioFile: '/audio/seychelles_english.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue aux Seychelles.',
      greetingEnglish: 'Hello! Welcome to Seychelles.',
      audioFile: '/audio/seychelles_french.mp3' },
  ]},
  SLE: { flag: '🇸🇱', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Sierra Leone.',
      greetingEnglish: 'Hello! Welcome to Sierra Leone.',
      audioFile: '/audio/sierra_leone_english.mp3' },
  ]},
  SSD: { flag: '🇸🇸', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to South Sudan.',
      greetingEnglish: 'Hello! Welcome to South Sudan.',
      audioFile: '/audio/south_sudan_english.mp3' },
    { language: 'Arabic', languageNative: 'العربية',
      greeting: 'مرحباً! أهلاً وسهلاً بكم في جنوب السودان',
      greetingEnglish: 'Hello! Welcome to South Sudan.',
      audioFile: '/audio/south_sudan_arabic.mp3' },
  ]},
  SWZ: { flag: '🇸🇿', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to eSwatini.',
      greetingEnglish: 'Hello! Welcome to eSwatini.',
      audioFile: '/audio/eswatini_english.mp3' },
  ]},
  UGA: { flag: '🇺🇬', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Uganda, the Pearl of Africa.',
      greetingEnglish: 'Hello! Welcome to Uganda, the Pearl of Africa.',
      audioFile: '/audio/uganda_english.mp3' },
    { language: 'Swahili', languageNative: 'Kiswahili',
      greeting: 'Habari! Karibu Uganda, Lulu ya Afrika.',
      greetingEnglish: 'Hello! Welcome to Uganda, the Pearl of Africa.',
      audioFile: '/audio/uganda_swahili.mp3' },
  ]},
  ZMB: { flag: '🇿🇲', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Zambia.',
      greetingEnglish: 'Hello! Welcome to Zambia.',
      audioFile: '/audio/zambia_english.mp3' },
  ]},
  ZWE: { flag: '🇿🇼', languages: [
    { language: 'Shona', languageNative: 'chiShona',
      greeting: 'Mhoro! Titambire kuZimbabwe.',
      greetingEnglish: 'Hello! Welcome to Zimbabwe.',
      audioFile: '/audio/zimbabwe_shona.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Zimbabwe.',
      greetingEnglish: 'Hello! Welcome to Zimbabwe.',
      audioFile: '/audio/zimbabwe_english.mp3' },
  ]},

  // ── Portuguese-speaking ──────────────────────────────────────────────────
  AGO: { flag: '🇦🇴', languages: [
    { language: 'Portuguese', languageNative: 'Português',
      greeting: 'Olá! Bem-vindo a Angola.',
      greetingEnglish: 'Hello! Welcome to Angola.',
      audioFile: '/audio/angola_portuguese.mp3' },
    { language: 'Lingala', languageNative: 'Lingála',
      greeting: 'Mbote! Boyei malamu na Angola.',
      greetingEnglish: 'Hello! Welcome to Angola.',
      audioFile: '/audio/angola_lingala.mp3' },
  ]},
  CPV: { flag: '🇨🇻', languages: [
    { language: 'Portuguese', languageNative: 'Português',
      greeting: 'Olá! Bem-vindo a Cabo Verde.',
      greetingEnglish: 'Hello! Welcome to Cabo Verde.',
      audioFile: '/audio/cabo_verde_portuguese.mp3' },
  ]},
  GNB: { flag: '🇬🇼', languages: [
    { language: 'Portuguese', languageNative: 'Português',
      greeting: 'Olá! Bem-vindo à Guiné-Bissau.',
      greetingEnglish: 'Hello! Welcome to Guinea-Bissau.',
      audioFile: '/audio/guinea_bissau_portuguese.mp3' },
  ]},
  MOZ: { flag: '🇲🇿', languages: [
    { language: 'Portuguese', languageNative: 'Português',
      greeting: 'Olá! Bem-vindo a Moçambique.',
      greetingEnglish: 'Hello! Welcome to Mozambique.',
      audioFile: '/audio/mozambique_portuguese.mp3' },
    { language: 'Swahili', languageNative: 'Kiswahili',
      greeting: 'Habari! Karibu Msumbiji.',
      greetingEnglish: 'Hello! Welcome to Mozambique.',
      audioFile: '/audio/mozambique_swahili.mp3' },
  ]},

  // ── Spanish-speaking ─────────────────────────────────────────────────────
  GNQ: { flag: '🇬🇶', languages: [
    { language: 'Spanish', languageNative: 'Español',
      greeting: '¡Hola! Bienvenido a Guinea Ecuatorial.',
      greetingEnglish: 'Hello! Welcome to Equatorial Guinea.',
      audioFile: '/audio/equatorial_guinea_spanish.mp3' },
    { language: 'French', languageNative: 'Français',
      greeting: 'Bonjour ! Bienvenue en Guinée équatoriale.',
      greetingEnglish: 'Hello! Welcome to Equatorial Guinea.',
      audioFile: '/audio/equatorial_guinea_french.mp3' },
  ]},

  // ── South Africa — multiple official languages ─────────────────────────
  ZAF: { flag: '🇿🇦', agentIntro: "South Africa has eleven official languages. Click again to hear greetings in isiXhosa and Afrikaans.", languages: [
    { language: 'isiZulu', languageNative: 'isiZulu',
      greeting: 'Sawubona! Uyemukelwa eNingizimu Afrika.',
      greetingEnglish: 'Hello! Welcome to South Africa.',
      audioFile: '/audio/south_africa_isizulu.mp3' },
    { language: 'isiXhosa', languageNative: 'isiXhosa',
      greeting: 'Molo! Wamkelekile eMzantsi Afrika.',
      greetingEnglish: 'Hello! Welcome to South Africa.',
      audioFile: '/audio/south_africa_isixhosa.mp3' },
    { language: 'Afrikaans', languageNative: 'Afrikaans',
      greeting: 'Hallo! Welkom in Suid-Afrika.',
      greetingEnglish: 'Hello! Welcome to South Africa.',
      audioFile: '/audio/south_africa_afrikaans.mp3' },
  ]},

  // ── Namibia — English primary per colleague request ─────────────────────
  NAM: { flag: '🇳🇦', languages: [
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Namibia.',
      greetingEnglish: 'Hello! Welcome to Namibia.',
      audioFile: '/audio/namibia_english.mp3' },
    { language: 'Afrikaans', languageNative: 'Afrikaans',
      greeting: 'Hallo! Welkom in Namibië.',
      greetingEnglish: 'Hello! Welcome to Namibia.',
      audioFile: '/audio/namibia_afrikaans.mp3' },
  ]},

  // ── Swahili ──────────────────────────────────────────────────────────────
  TZA: { flag: '🇹🇿', languages: [
    { language: 'Swahili', languageNative: 'Kiswahili',
      greeting: 'Habari! Karibu Tanzania.',
      greetingEnglish: 'Hello! Welcome to Tanzania.',
      audioFile: '/audio/tanzania_swahili.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Tanzania.',
      greetingEnglish: 'Hello! Welcome to Tanzania.',
      audioFile: '/audio/tanzania_english.mp3' },
  ]},

  // ── Amharic ──────────────────────────────────────────────────────────────
  ETH: { flag: '🇪🇹', languages: [
    { language: 'Amharic', languageNative: 'አማርኛ',
      greeting: 'ሰላም! ወደ ኢትዮጵያ እንኳን ደህና መጡ።',
      greetingEnglish: 'Hello! Welcome to Ethiopia.',
      audioFile: '/audio/ethiopia_amharic.mp3' },
    { language: 'English', languageNative: 'English',
      greeting: 'Hello! Welcome to Ethiopia.',
      greetingEnglish: 'Hello! Welcome to Ethiopia.',
      audioFile: '/audio/ethiopia_english.mp3' },
  ]},
};

// Compute stats once
const ALL_LANGUAGES = (() => {
  const langs = new Set();
  Object.values(COUNTRY_DATA).forEach(c => c.languages.forEach(l => langs.add(l.language)));
  return [...langs].sort();
})();
const TOTAL_COUNTRIES = Object.keys(COUNTRY_DATA).length;

function getCountryInfo(iso3) {
  if (COUNTRY_DATA[iso3]) return { ...COUNTRY_DATA[iso3], hasAudio: true };
  return null;
}

// =============================================================================
// Geo → SVG projection helpers
// =============================================================================

function mercatorY(lat) {
  const latRad = (lat * Math.PI) / 180;
  return Math.log(Math.tan(Math.PI / 4 + latRad / 2));
}

function projectPoint(lon, lat, bounds, width, height, padding = 20) {
  const { minLon, maxLon, minLat, maxLat } = bounds;
  const x = ((lon - minLon) / (maxLon - minLon)) * (width - padding * 2) + padding;
  const yMin = mercatorY(minLat);
  const yMax = mercatorY(maxLat);
  const yMerc = mercatorY(lat);
  const y = (1 - (yMerc - yMin) / (yMax - yMin)) * (height - padding * 2) + padding;
  return [x, y];
}

function geoToSvgPath(geometry, bounds, width, height) {
  const coords =
    geometry.type === 'Polygon'
      ? [geometry.coordinates]
      : geometry.type === 'MultiPolygon'
        ? geometry.coordinates
        : [];

  return coords
    .map((polygon) =>
      polygon
        .map((ring) =>
          ring
            .map(([lon, lat], i) => {
              const [x, y] = projectPoint(lon, lat, bounds, width, height);
              return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
            })
            .join(' ') + ' Z'
        )
        .join(' ')
    )
    .join(' ');
}

function getGeoBounds(features) {
  let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
  for (const feat of features) {
    const coords =
      feat.geometry.type === 'Polygon'
        ? feat.geometry.coordinates.flat()
        : feat.geometry.type === 'MultiPolygon'
          ? feat.geometry.coordinates.flat(2)
          : [];
    for (const [lon, lat] of coords) {
      if (lon < minLon) minLon = lon;
      if (lon > maxLon) maxLon = lon;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    }
  }
  return { minLon, maxLon, minLat, maxLat };
}

function getCentroid(geometry) {
  const coords =
    geometry.type === 'Polygon'
      ? geometry.coordinates[0]
      : geometry.type === 'MultiPolygon'
        ? geometry.coordinates.reduce((a, b) => (b[0].length > a.length ? b[0] : a), [])
        : [];
  if (!coords.length) return [0, 0];
  let cx = 0, cy = 0;
  for (const [lon, lat] of coords) { cx += lon; cy += lat; }
  return [cx / coords.length, cy / coords.length];
}

// =============================================================================
// Waveform visualizer
// =============================================================================

const WaveformVisualizer = ({ isPlaying }) => {
  const bars = 24;
  return (
    <div className="audio-waveform flex items-end gap-[2px] h-8">
      {Array.from({ length: bars }).map((_, i) => (
        <div
          key={i}
          className={`waveform-bar ${isPlaying ? 'waveform-bar-active' : ''}`}
          style={{
            animationDelay: `${i * 0.05}s`,
            height: isPlaying ? undefined : '3px',
          }}
        />
      ))}
    </div>
  );
};

// =============================================================================
// Main Component
// =============================================================================

export default function AudioExplorationTab() {
  const [geoData, setGeoData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hoveredCountry, setHoveredCountry] = useState(null);
  const [activeCountry, setActiveCountry] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioError, setAudioError] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [voiceMode, setVoiceMode] = useState('one-voice'); // 'one-voice' | 'local'
  const [langIndexMap, setLangIndexMap] = useState({}); // { [iso3]: number }
  const audioRef = useRef(null);
  const svgRef = useRef(null);
  const containerRef = useRef(null);

  const SVG_WIDTH = 800;
  const SVG_HEIGHT = 900;

  // Load GeoJSON
  useEffect(() => {
    fetch('/data/africa_boundaries.geojson')
      .then((r) => r.json())
      .then((data) => {
        setGeoData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load GeoJSON:', err);
        setLoading(false);
      });
  }, []);

  // Precompute SVG paths
  const { countryPaths, bounds } = useMemo(() => {
    if (!geoData) return { countryPaths: [], bounds: null };
    const b = getGeoBounds(geoData.features);
    // Add padding
    const lonPad = (b.maxLon - b.minLon) * 0.02;
    const latPad = (b.maxLat - b.minLat) * 0.02;
    const paddedBounds = {
      minLon: b.minLon - lonPad,
      maxLon: b.maxLon + lonPad,
      minLat: b.minLat - latPad,
      maxLat: b.maxLat + latPad,
    };

    const paths = geoData.features.map((feat) => {
      const iso3 = feat.properties.iso3;
      const name = feat.properties.name;
      const d = geoToSvgPath(feat.geometry, paddedBounds, SVG_WIDTH, SVG_HEIGHT);
      const [cLon, cLat] = getCentroid(feat.geometry);
      const [cx, cy] = projectPoint(cLon, cLat, paddedBounds, SVG_WIDTH, SVG_HEIGHT);
      const info = getCountryInfo(iso3);
      return { iso3, name, d, cx, cy, info };
    });

    return { countryPaths: paths, bounds: paddedBounds };
  }, [geoData]);

  // Audio management — use refs to avoid stale closures
  const activeCountryRef = useRef(null);
  const isPlayingRef = useRef(false);
  const langIndexMapRef = useRef({});

  // Keep refs in sync
  isPlayingRef.current = isPlaying;
  langIndexMapRef.current = langIndexMap;

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current.removeAttribute('src');
      audioRef.current = null;
    }
    setIsPlaying(false);
    setAudioError(null);
  }, []);

  const voiceModeRef = useRef(voiceMode);
  voiceModeRef.current = voiceMode;

  const playAudio = useCallback((langEntry) => {
    // Always fully stop any existing audio first
    stopAudio();

    setAudioError(null);
    // Swap path prefix based on voice mode
    const audioPath = voiceModeRef.current === 'local'
      ? langEntry.audioFile.replace('/audio/', '/audio/local/')
      : langEntry.audioFile;
    const audio = new Audio(audioPath);
    audioRef.current = audio;

    audio.addEventListener('canplaythrough', () => {
      // Guard: only play if this audio is still the current one
      if (audioRef.current !== audio) {
        audio.pause();
        return;
      }
      audio.play().catch(() => setAudioError('Playback blocked'));
      setIsPlaying(true);
    });

    audio.addEventListener('ended', () => {
      if (audioRef.current === audio) {
        setIsPlaying(false);
      }
    });

    audio.addEventListener('error', () => {
      if (audioRef.current === audio) {
        setAudioError('Audio not yet generated');
        setIsPlaying(false);
      }
    });

    audio.load();
  }, [stopAudio]);

  // Mouse leave always stops audio unconditionally and resets language index
  const handleMouseLeave = useCallback((iso3) => {
    setHoveredCountry(null);
    // If this was the active country, stop everything
    if (activeCountryRef.current === iso3) {
      stopAudio();
      setActiveCountry(null);
      activeCountryRef.current = null;
      setLangIndexMap(prev => ({ ...prev, [iso3]: 0 }));
    }
  }, [stopAudio]);

  const handleMouseEnter = useCallback((iso3) => {
    setHoveredCountry(iso3);
  }, []);

  const handleClick = useCallback((iso3) => {
    const data = COUNTRY_DATA[iso3];
    if (!data?.languages?.length) return;

    const totalLangs = data.languages.length;

    if (activeCountryRef.current === iso3) {
      // Same country clicked again
      if (isPlayingRef.current && totalLangs > 1) {
        // Currently playing — cycle to next language
        const currentIdx = langIndexMapRef.current[iso3] || 0;
        const nextIdx = (currentIdx + 1) % totalLangs;
        setLangIndexMap(prev => ({ ...prev, [iso3]: nextIdx }));
        stopAudio();
        playAudio(data.languages[nextIdx]);
      } else {
        // Not playing or single language — toggle off
        stopAudio();
        setActiveCountry(null);
        activeCountryRef.current = null;
        setLangIndexMap(prev => ({ ...prev, [iso3]: 0 }));
      }
    } else {
      // New country clicked — start with primary language
      stopAudio();
      const startIdx = 0;
      setLangIndexMap(prev => ({ ...prev, [iso3]: startIdx }));
      setActiveCountry(iso3);
      activeCountryRef.current = iso3;
      playAudio(data.languages[startIdx]);
    }
  }, [playAudio, stopAudio]);

  // Track mouse position for tooltip
  const handleMouseMove = useCallback((e) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }, []);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const hoveredInfo = hoveredCountry ? getCountryInfo(hoveredCountry) : null;
  const hoveredName = hoveredCountry
    ? countryPaths.find((c) => c.iso3 === hoveredCountry)?.name
    : null;

  // Current language for active country
  const activeLangIdx = activeCountry ? (langIndexMap[activeCountry] || 0) : 0;
  const activeData = activeCountry ? COUNTRY_DATA[activeCountry] : null;
  const activeLang = activeData ? activeData.languages[activeLangIdx] : null;

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-lg">Loading map...</div>
      </div>
    );
  }

  return (
    <div className="audio-exploration-page h-full overflow-hidden">
      {/* Background texture */}
      <div className="audio-bg-texture" />

      <div className="max-w-[1800px] mx-auto px-6 py-6 h-full flex flex-col">
        {/* Hero header */}
        <div className="text-center mb-6 relative z-10">
          <h1 className="audio-title text-4xl font-bold tracking-tight mb-2">
            Voices of Africa
          </h1>
          <p className="text-slate-400 text-base max-w-xl mx-auto leading-relaxed">
            Hover over a country to see its languages. Click to hear a greeting
            — click again to cycle through additional languages.
          </p>
          {/* Voice mode toggle */}
          <div className="voice-mode-toggle mt-4">
            <button
              className={`voice-mode-btn ${voiceMode === 'one-voice' ? 'voice-mode-btn-active' : ''}`}
              onClick={() => { stopAudio(); setActiveCountry(null); activeCountryRef.current = null; setLangIndexMap({}); setVoiceMode('one-voice'); }}
            >
              <Mic className="w-3.5 h-3.5" />
              One Voice
            </button>
            <button
              className={`voice-mode-btn ${voiceMode === 'local' ? 'voice-mode-btn-active' : ''}`}
              onClick={() => { stopAudio(); setActiveCountry(null); activeCountryRef.current = null; setLangIndexMap({}); setVoiceMode('local'); }}
            >
              <Globe className="w-3.5 h-3.5" />
              Local Voices
            </button>
          </div>
          <div className="text-xs text-slate-400 mt-2">
            {voiceMode === 'one-voice'
              ? 'Same speaker across all languages — compare how one voice handles each language'
              : 'Region-appropriate African voices — hear how a local speaker sounds'}
          </div>

          <div className="flex items-center justify-center gap-6 mt-3">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-amber-400/80" />
              <span className="text-xs text-slate-500">Click to hear greeting</span>
            </div>
            <div className="text-xs text-slate-400">{TOTAL_COUNTRIES} countries &middot; {ALL_LANGUAGES.length} languages</div>
          </div>
        </div>

        {/* Map + sidebar */}
        <div className="flex-1 flex gap-6 min-h-0">
          {/* SVG Map */}
          <div
            ref={containerRef}
            className="flex-1 relative"
            onMouseMove={handleMouseMove}
          >
            <svg
              ref={svgRef}
              viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
              className="w-full h-full"
              style={{ maxHeight: 'calc(100vh - 240px)' }}
            >
              {/* Defs for filters and gradients */}
              <defs>
                <filter id="glow-amber" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="6" result="blur" />
                  <feFlood floodColor="#f59e0b" floodOpacity="0.4" result="color" />
                  <feComposite in="color" in2="blur" operator="in" result="shadow" />
                  <feMerge>
                    <feMergeNode in="shadow" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <filter id="glow-active" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="10" result="blur" />
                  <feFlood floodColor="#f59e0b" floodOpacity="0.7" result="color" />
                  <feComposite in="color" in2="blur" operator="in" result="shadow" />
                  <feMerge>
                    <feMergeNode in="shadow" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <filter id="glow-slate" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="4" result="blur" />
                  <feFlood floodColor="#94a3b8" floodOpacity="0.3" result="color" />
                  <feComposite in="color" in2="blur" operator="in" result="shadow" />
                  <feMerge>
                    <feMergeNode in="shadow" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <linearGradient id="country-audio-fill" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#fbbf24" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#d97706" stopOpacity="0.15" />
                </linearGradient>
                <linearGradient id="country-audio-hover" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#fbbf24" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.35" />
                </linearGradient>
                <linearGradient id="country-active" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#fbbf24" stopOpacity="0.7" />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.55" />
                </linearGradient>
                <linearGradient id="country-default" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#e2e8f0" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#cbd5e1" stopOpacity="0.3" />
                </linearGradient>
                <linearGradient id="country-default-hover" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#cbd5e1" stopOpacity="0.6" />
                  <stop offset="100%" stopColor="#94a3b8" stopOpacity="0.4" />
                </linearGradient>
              </defs>

              {/* Country paths */}
              {countryPaths.map(({ iso3, name, d, info }) => {
                const hasAudio = info?.hasAudio;
                const isHovered = hoveredCountry === iso3;
                const isActive = activeCountry === iso3;

                let fill, stroke, strokeWidth, filter;
                if (isActive) {
                  fill = 'url(#country-active)';
                  stroke = '#f59e0b';
                  strokeWidth = 2;
                  filter = 'url(#glow-active)';
                } else if (isHovered && hasAudio) {
                  fill = 'url(#country-audio-hover)';
                  stroke = '#f59e0b';
                  strokeWidth = 1.5;
                  filter = 'url(#glow-amber)';
                } else if (isHovered) {
                  fill = 'url(#country-default-hover)';
                  stroke = '#94a3b8';
                  strokeWidth = 1.5;
                  filter = 'url(#glow-slate)';
                } else if (hasAudio) {
                  fill = 'url(#country-audio-fill)';
                  stroke = '#d97706';
                  strokeWidth = 0.8;
                  filter = 'none';
                } else {
                  fill = 'url(#country-default)';
                  stroke = '#94a3b8';
                  strokeWidth = 0.5;
                  filter = 'none';
                }

                return (
                  <path
                    key={iso3}
                    d={d}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={strokeWidth}
                    filter={filter}
                    className={`country-path ${hasAudio ? 'country-has-audio' : 'country-no-audio'} ${isActive ? 'country-active' : ''}`}
                    onMouseEnter={(e) => handleMouseEnter(iso3, e)}
                    onMouseLeave={() => handleMouseLeave(iso3)}
                    onClick={() => handleClick(iso3)}
                    style={{ cursor: hasAudio ? 'pointer' : 'default' }}
                  />
                );
              })}
            </svg>

            {/* Floating tooltip */}
            {hoveredCountry && hoveredInfo && (
              <div
                className="audio-tooltip"
                style={{
                  left: mousePos.x + 16,
                  top: mousePos.y - 10,
                  pointerEvents: 'none',
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">{hoveredInfo.flag || '🌍'}</span>
                  <span className="font-semibold text-slate-800">{hoveredName}</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Globe className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-slate-600">
                    {hoveredInfo.languages.map(l => l.language).join(' / ')}
                  </span>
                </div>
                {hoveredInfo.hasAudio && (
                  <div className="flex items-center gap-1.5 mt-1.5 text-xs text-amber-600">
                    <Volume2 className="w-3 h-3" />
                    {hoveredInfo.languages.length > 1
                      ? 'Click to hear greeting \u00b7 click again to cycle'
                      : 'Click to hear greeting'}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Sidebar — active country detail */}
          <div className="w-80 flex flex-col gap-4">
            {/* Now playing card */}
            <div className={`audio-now-playing-card ${activeCountry ? 'card-active' : ''}`}>
              {activeCountry && activeData && activeLang ? (
                <>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="audio-speaker-icon">
                      {isPlaying ? (
                        <Volume2 className="w-5 h-5 text-amber-500" />
                      ) : (
                        <VolumeX className="w-5 h-5 text-slate-400" />
                      )}
                    </div>
                    <div>
                      <div className="font-semibold text-slate-800 text-lg">
                        {countryPaths.find((c) => c.iso3 === activeCountry)?.name}
                      </div>
                      <div className="text-sm text-slate-500">
                        {activeLang.language}
                        {activeLang.languageNative !== activeLang.language && (
                          <span className="text-slate-400 ml-1">({activeLang.languageNative})</span>
                        )}
                      </div>
                      {/* Language dot indicators */}
                      {activeData.languages.length > 1 && (
                        <div className="flex items-center gap-1.5 mt-1.5">
                          {activeData.languages.map((lang, i) => (
                            <div
                              key={i}
                              className={`w-2 h-2 rounded-full transition-colors ${
                                i === activeLangIdx ? 'bg-amber-500' : 'bg-slate-300'
                              }`}
                              title={lang.language}
                            />
                          ))}
                          <span className="text-xs text-slate-400 ml-1">
                            {activeLangIdx + 1}/{activeData.languages.length}
                          </span>
                        </div>
                      )}
                    </div>
                    <span className="text-2xl ml-auto">{activeData.flag}</span>
                  </div>

                  {/* Waveform */}
                  <div className="mb-4">
                    <WaveformVisualizer isPlaying={isPlaying} />
                  </div>

                  {/* Greeting text */}
                  <div className="bg-slate-50 rounded-xl p-4 mb-3 border border-slate-100">
                    <div className="text-base font-medium text-slate-700 leading-relaxed" dir="auto">
                      &ldquo;{activeLang.greeting}&rdquo;
                    </div>
                    <div className="text-sm text-slate-400 mt-2 italic">
                      {activeLang.greetingEnglish}
                    </div>
                  </div>

                  {/* Agent description */}
                  {activeData.agentIntro && (
                    <p className="text-sm text-slate-500 leading-relaxed">
                      {activeData.agentIntro}
                    </p>
                  )}

                  {audioError && (
                    <div className="mt-3 text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2 border border-amber-100">
                      <Mic className="w-3 h-3 inline mr-1" />
                      {audioError} — run the generation script to create audio files.
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-12">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-50 flex items-center justify-center">
                    <Volume2 className="w-7 h-7 text-slate-300" />
                  </div>
                  <div className="text-slate-400 text-sm mb-1">Click a highlighted country</div>
                  <div className="text-slate-300 text-xs">to hear an AI greeting</div>
                </div>
              )}
            </div>

            {/* Info card */}
            <div className="audio-info-card">
              <div className="flex items-center gap-2 mb-3">
                <Mic className="w-4 h-4 text-amber-500" />
                <span className="text-sm font-semibold text-slate-700">Powered by ElevenLabs</span>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Each greeting is synthesized using ElevenLabs' multilingual text-to-speech models,
                demonstrating how AI agents can communicate naturally in local languages across the continent.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {ALL_LANGUAGES.map(lang => (
                  <span key={lang} className="audio-tag">{lang}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
