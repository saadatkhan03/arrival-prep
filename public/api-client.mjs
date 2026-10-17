export class ApiError extends Error {constructor(message,status){super(message);this.status=status;}}
export class ApiClient {
 constructor(){this.csrf='';}
 async request(path,body,options={}){
  const headers={...(options.headers||{})};if(body!==undefined){headers['Content-Type']='application/json';headers['X-Session-Token']=this.csrf;}
  const r=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers,...(body===undefined?{}:{body:JSON.stringify(body)}),signal:options.signal});
  if(!r.ok){let j;try{j=await r.json();}catch{j={error:'The service could not complete this request.'};}throw new ApiError(j.error||'Request failed.',r.status);}
  return options.blob?r.blob():r.json();
 }
 async initialize(){const config=await this.request('/api/config');this.csrf=config.token;return config;}
}
