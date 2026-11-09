 'use strict';
function unicode(s){for(let i=0;i<s.length;i++){const c=s.charCodeAt(i);if(c>=0xD800&&c<=0xDBFF){const d=s.charCodeAt(++i);if(!(d>=0xDC00&&d<=0xDFFF))throw Error('Unpaired Unicode surrogate');}else if(c>=0xDC00&&c<=0xDFFF)throw Error('Unpaired Unicode surrogate');}}
function number(s){const n=Number(s);if(!Number.isFinite(n)||(Number.isInteger(n)&&!Number.isSafeInteger(n)))throw Error('Nonfinite or unsafe JSON number');if(n===0&&/[1-9]/.test(s.split(/[eE]/)[0]))throw Error('Nonzero numeric underflow');}
module.exports={unicode,number};
