'use strict';
// Reproducible, dependency-free source ZIP for Netlify's build workflow.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),{crc32}=require('node:zlib');
require('./build.js');
const root=path.resolve(__dirname,'..'),out=path.join(root,'outputs/netlify');
const roots=['.gitignore','AGENTS.md','README.md','package.json','requirements-dev.txt','netlify.toml','src','tools','docs','tests'];
const excluded=name=>name==='.DS_Store'||name.startsWith('._')||['__pycache__','outputs','node_modules','.git','.env','.openai'].includes(name);
const files=[];
function collect(relative){
  const absolute=path.join(root,relative),stat=fs.lstatSync(absolute);
  if(stat.isSymbolicLink())throw Error('Não é permitido empacotar links simbólicos: '+relative);
  if(stat.isDirectory()){for(const name of fs.readdirSync(absolute).sort())if(!excluded(name))collect(path.join(relative,name));}
  else if(stat.isFile())files.push(relative);
  else throw Error('Tipo de arquivo não suportado: '+relative);
}
for(const name of roots)collect(name);
files.sort();if(files.length>65535)throw Error('Arquivos demais para o pacote ZIP.');
const local=[],central=[],manifest=[];let offset=0,total=0;
for(const relative of files){
  const name=Buffer.from(relative.split(path.sep).join('/'),'utf8'),data=fs.readFileSync(path.join(root,relative));
  total+=data.length;if(total>128*1024*1024||name.length>65535)throw Error('Pacote excede o limite de128MiB ou de nome de arquivo.');
  const crc=crc32(data),header=Buffer.alloc(30);header.writeUInt32LE(0x04034b50,0);header.writeUInt16LE(20,4);header.writeUInt16LE(0x800,6);header.writeUInt16LE(0x21,12);header.writeUInt32LE(crc,14);header.writeUInt32LE(data.length,18);header.writeUInt32LE(data.length,22);header.writeUInt16LE(name.length,26);
  const entry=Buffer.alloc(46);entry.writeUInt32LE(0x02014b50,0);entry.writeUInt16LE(20,4);entry.writeUInt16LE(20,6);entry.writeUInt16LE(0x800,8);entry.writeUInt16LE(0x21,14);entry.writeUInt32LE(crc,16);entry.writeUInt32LE(data.length,20);entry.writeUInt32LE(data.length,24);entry.writeUInt16LE(name.length,28);entry.writeUInt32LE(offset,42);
  local.push(header,name,data);central.push(entry,name);offset+=header.length+name.length+data.length;
  manifest.push({path:name.toString(),bytes:data.length,sha256:crypto.createHash('sha256').update(data).digest('hex')});
}
const directory=Buffer.concat(central),end=Buffer.alloc(22);end.writeUInt32LE(0x06054b50,0);end.writeUInt16LE(files.length,8);end.writeUInt16LE(files.length,10);end.writeUInt32LE(directory.length,12);end.writeUInt32LE(offset,16);
const archive=Buffer.concat([...local,directory,end]),filename=path.join(out,'planejamento-patrimonial-netlify-fonte.zip');
fs.mkdirSync(out,{recursive:true});const temporary=filename+'.tmp';fs.writeFileSync(temporary,archive);fs.renameSync(temporary,filename);
fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify({candidate:fs.readFileSync(path.join(root,'dist/assets/version.js'),'utf8').match(/PP_BUILD="([^"]+)"/)[1],sha256:crypto.createHash('sha256').update(archive).digest('hex'),files:manifest},null,2)+'\n');
console.log('NETLIFY ZIP '+filename+' ('+files.length+' arquivos; src/site incluído; dist será gerada pelo build)');
