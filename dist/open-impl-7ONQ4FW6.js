import {createRequire as __createRequire} from 'module';var require=__createRequire(import.meta.url);
import{a as r}from"./chunk-5XX4NC7F.js";import{f as n,h as o}from"./chunk-7YQV5RAR.js";async function l(e,a){let t=await r(this,a,e.language??"en");if(!t.url)throw new o("No results found");await this.open(t.url),this.process.stdout.write(`Opening ${n.blue.underline(t.url)}
`)}export{l as default};
