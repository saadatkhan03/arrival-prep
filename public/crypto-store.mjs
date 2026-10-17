import {encryptBackup,decryptBackup} from './backup.mjs';
const random=()=>Array.from(crypto.getRandomValues(new Uint8Array(32)),v=>v.toString(16).padStart(2,'0')).join('');
export async function newKeys(password){const key=random(),recovery=random();return {key,recovery,password_wrap:await encryptBackup({key},password),recovery_wrap:await encryptBackup({key},recovery)};}
export async function unlockKey(wrap,password){const data=await decryptBackup(wrap,password);if(!/^[0-9a-f]{64}$/.test(data.key||''))throw Error('The encryption key is invalid.');return data.key;}
export async function rewrapKey(key,password){return encryptBackup({key},password);}
export {encryptBackup,decryptBackup};
