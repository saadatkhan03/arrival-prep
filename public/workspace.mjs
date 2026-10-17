/** Serial saves bound to an immutable account/application generation. */
export class Workspace {
 constructor({request,encrypt,onStatus=()=>{},delay=700}){this.request=request;this.encrypt=encrypt;this.onStatus=onStatus;this.delay=delay;this.generation=0;this.context=null;this.timer=null;this.running=null;this.serial=0;this.savedSerial=0;this.failure=null;this.snapshot=null;}
 bind({userId,applicationId,key,version=0}){if(this.running)throw Error('Wait for the current save before switching applications.');this.invalidate();this.context=Object.freeze({userId,applicationId,key,generation:this.generation});this.version=version;this.serial=0;this.savedSerial=0;this.failure=null;this.onStatus('saved','No unsaved changes');}
 invalidate(){clearTimeout(this.timer);this.generation++;this.controller?.abort();this.context=null;this.snapshot=null;this.failure=null;}
 get dirty(){return this.serial!==this.savedSerial;}
 changed(snapshot){if(!this.context)throw Error('Unlock the application first.');this.snapshot=structuredClone(snapshot);this.serial++;this.onStatus('saving','Waiting to save…');clearTimeout(this.timer);this.timer=setTimeout(()=>this.flush().catch(()=>{}),this.delay);}
 async flush(){
  clearTimeout(this.timer);if(this.failure)throw this.failure;if(this.running){await this.running;return this.flush();}if(!this.context||!this.dirty)return;
  const context=this.context,serial=this.serial,snapshot=structuredClone(this.snapshot);this.controller=new AbortController();const signal=this.controller.signal;
  const current=()=>this.context===context&&context.generation===this.generation;
  this.running=(async()=>{
   try{
    this.onStatus('saving','Encrypting and saving…');const envelope=await this.encrypt(snapshot,context.key);if(!current())return;
    const response=await this.request('/api/dossier',{application_id:context.applicationId,account_id:context.userId,expected_version:this.version,encrypted_blob:envelope,section_count:snapshot.sectionCount||0,evidence_count:snapshot.data?.sections?.evidence?.length||0},{signal});
    if(!current())return;this.version=response.version;this.savedSerial=serial;this.onStatus(this.dirty?'saving':'saved',this.dirty?'Saving newer changes…':'Saved to your account · revision '+this.version);
   }catch(error){if(!current()||error.name==='AbortError')return;this.failure=error;this.onStatus('failed',error.status===409?'Conflict: another tab saved changes. Download a backup before reloading.':'Save failed: '+error.message);throw error;}
  })();
  try{await this.running;}finally{this.running=null;}
  if(current()&&this.dirty)return this.flush();
 }
 retry(){this.failure=null;return this.flush();}
}
