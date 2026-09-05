import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve("frontend/dist");
let paid = false;
const rootPage = {id:"root",title:"Переезд в Бразилию",document:[{type:"callout",icon:"🇧🇷",rich_text:[{text:"Пошаговый гид: документы, жильё и первые недели после переезда.",annotations:{bold:true}}]},{type:"heading_2",rich_text:[{text:"С чего начать"}]},{type:"paragraph",rich_text:[{text:"Мы собрали проверенные материалы, чтобы вы не терялись в десятках вкладок."}]},{type:"image",image_id:"demo",caption:"Рио-де-Жанейро"}],children:[{id:"free",title:"Подготовка документов",locked:false},{id:"paid",title:"Проверенные специалисты и контакты",locked:!paid}]};
const pages={free:{id:"free",title:"Подготовка документов",document:[{type:"paragraph",rich_text:[{text:"Составьте цифровые копии документов и проверьте срок действия паспорта."}]},{type:"to_do",checked:true,rich_text:[{text:"Паспорт и заверенные переводы"}]},{type:"to_do",checked:false,rich_text:[{text:"Апостиль и справки"}]}],children:[]},paid:{id:"paid",title:"Проверенные специалисты",document:[{type:"callout",icon:"✓",rich_text:[{text:"Доступ открыт. Здесь отображаются платные материалы."}]}],children:[]}};
const image=Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII=","base64");
const json=(res,status,value)=>{res.writeHead(status,{"content-type":"application/json"});res.end(JSON.stringify(value))};
http.createServer((req,res)=>{
 const url=new URL(req.url,"http://localhost");
 if(url.pathname==="/api/countries/brazil") return json(res,200,{slug:"brazil",title:"Бразилия",flag:"🇧🇷",root_page_id:"root",paid});
 if(url.pathname==="/api/pages/root") return json(res,200,{...rootPage,children:rootPage.children.map(x=>x.id==="paid"?{...x,locked:!paid}:x)});
 if(url.pathname==="/api/pages/paid"&&!paid) return json(res,402,{detail:"Country access required"});
 if(url.pathname.startsWith("/api/pages/")) return json(res,200,pages[url.pathname.split("/").at(-1)]);
 if(url.pathname==="/api/countries/brazil/purchase"&&req.method==="POST"){paid=true;return json(res,200,{status:"succeeded",provider:"stub"})}
 if(url.pathname==="/api/images/demo"){res.writeHead(200,{"content-type":"image/png"});return res.end(image)}
 const file=url.pathname==="/"?"index.html":url.pathname.slice(1);const target=path.join(root,file);
 if(target.startsWith(root)&&fs.existsSync(target)){res.writeHead(200,{"content-type":target.endsWith(".js")?"text/javascript":target.endsWith(".css")?"text/css":"text/html"});return fs.createReadStream(target).pipe(res)}
 fs.createReadStream(path.join(root,"index.html")).pipe(res);
}).listen(4173,"0.0.0.0",()=>console.log("E2E server ready at http://localhost:4173"));
