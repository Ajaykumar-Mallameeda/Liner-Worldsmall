/**
 * portLookup.js
 * -------------
 * Authoritative port names and metadata for maritime port codes.
 */

import portCoords from '../assets/port_coordinates.json';

const PORT_NAMES = {
  CNSHA: 'Shanghai',
  CNNGB: 'Ningbo-Zhoushan',
  CNSZX: 'Shenzhen',
  CNQDG: 'Qingdao',
  CNGZG: 'Guangzhou',
  CNTNJ: 'Tianjin',
  CNYTN: 'Yantian',
  CNXMN: 'Xiamen',
  CNDAL: 'Dalian',
  CNFOC: 'Fuzhou',
  HKHKG: 'Hong Kong',
  SGSIN: 'Singapore',
  MYPKG: 'Port Klang',
  MYTPP: 'Tanjung Pelepas',
  KRPUS: 'Busan',
  KRINC: 'Incheon',
  JPYOK: 'Yokohama',
  JPTYO: 'Tokyo',
  JPKOB: 'Kobe',
  JPOSA: 'Osaka',
  JPUKB: 'Kobe',
  TWKHH: 'Kaohsiung',
  AUMEL: 'Melbourne',
  AUSYD: 'Sydney',
  AUBNE: 'Brisbane',
  AUFRE: 'Fremantle',
  NLRTM: 'Rotterdam',
  BEANR: 'Antwerp',
  DEHAM: 'Hamburg',
  DEBRV: 'Bremerhaven',
  GBFXT: 'Felixstowe',
  GBLON: 'London Gateway',
  GBSOU: 'Southampton',
  FRLEH: 'Le Havre',
  FRMRS: 'Marseille-Fos',
  FRBES: 'Brest',
  FRURO: 'Rouen',
  ESVLC: 'Valencia',
  ESALG: 'Algeciras',
  ESBCN: 'Barcelona',
  ITGOA: 'Genoa',
  ITTRS: 'Trieste',
  ITSPE: 'La Spezia',
  GRPIR: 'Piraeus',
  MTMLA: 'Marsaxlokk',
  CYLMS: 'Limassol',
  TRIST: 'Istanbul',
  USLAX: 'Los Angeles',
  USLGB: 'Long Beach',
  USNYC: 'New York/NJ',
  USENY: 'New York',
  USSAV: 'Savannah',
  USCHS: 'Charleston',
  USHOU: 'Houston',
  USOAK: 'Oakland',
  USSEA: 'Seattle',
  USTAC: 'Tacoma',
  USMIA: 'Miami',
  USBAL: 'Baltimore',
  USORF: 'Norfolk',
  USLIM: 'Lima',
  CAVAN: 'Vancouver',
  CAMTR: 'Montreal',
  CAPRR: 'Prince Rupert',
  MXMZT: 'Manzanillo (MX)',
  MXLZC: 'Lazaro Cardenas',
  PAONX: 'Colon / Manzanillo',
  PABLB: 'Balboa',
  BRSSZ: 'Santos',
  BRPRG: 'Paranagua',
  BRRIG: 'Rio Grande',
  BRVIX: 'Vitoria',
  ARBUE: 'Buenos Aires',
  ARPMY: 'Puerto Madryn',
  ARPUD: 'Puerto Deseado',
  CLVAP: 'Valparaiso',
  CLSAI: 'San Antonio',
  CLARI: 'Arica',
  ECGYE: 'Guayaquil',
  COCTG: 'Cartagena',
  AEJEA: 'Jebel Ali',
  AEDXB: 'Dubai',
  AEAUH: 'Abu Dhabi',
  AEKHL: 'Khalifa',
  SAJED: 'Jeddah',
  SADMM: 'Dammam',
  OMSLL: 'Salalah',
  QAHMD: 'Hamad',
  KHKWT: 'Kuwait',
  BHKBS: 'Khalifa Bin Salman',
  SYLTK: 'Lattakia',
  EGPSD: 'Port Said',
  EGDAM: 'Damietta',
  EGALY: 'Alexandria',
  EGSOC: 'Sokhna',
  ZACPT: 'Cape Town',
  ZAJUR: 'Durban',
  ZAPLZ: 'Port Elizabeth',
  ZANPL: 'Ngqura',
  KEMBA: 'Mombasa',
  TZDAR: 'Dar es Salaam',
  DJJIB: 'Djibouti',
  NGAPP: 'Apapa (Lagos)',
  NGTIN: 'Tin Can (Lagos)',
  GHSTA: 'Tema',
  CIABJ: 'Abidjan',
  SNDKR: 'Dakar',
  TGLFW: 'Lome',
  AOLAD: 'Luanda',
  AOLOB: 'Lobito',
  LKCMB: 'Colombo',
  INNSA: 'Nhava Sheva (JNPT)',
  INMUN: 'Mundra',
  INMAA: 'Chennai',
  INCOK: 'Cochin',
  BDCGP: 'Chittagong',
  PKBQM: 'Port Qasim',
  PKKHI: 'Karachi',
  THLCH: 'Laem Chabang',
  VNSGN: 'Ho Chi Minh City',
  VNHPH: 'Hai Phong',
  IDTPP: 'Tanjung Priok (Jakarta)',
  IDSUB: 'Surabaya',
  PHMNL: 'Manila',
};

export function getPortName(portCode) {
  if (!portCode) return 'Unknown Port';
  const code = String(portCode).toUpperCase().trim();
  return PORT_NAMES[code] || `Port ${code}`;
}

export function getPortFullLabel(portCode) {
  if (!portCode) return '—';
  const code = String(portCode).toUpperCase().trim();
  const name = PORT_NAMES[code];
  return name ? `${name} (${code})` : code;
}

export function getPortCoordinates(portCode) {
  if (!portCode) return null;
  const code = String(portCode).toUpperCase().trim();
  if (portCoords[code]) {
    // portCoords is [lat, lng] -> convert to [lng, lat]
    return [portCoords[code][1], portCoords[code][0]];
  }
  return null;
}
