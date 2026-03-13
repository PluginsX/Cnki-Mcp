var currentAgreementVersions = "250615";
AppendJs("https://login.cnki.net/toploginnew/scripts/ecpAgreementAlertHandle.js");
 // AppendJs("http://e.dev.cnki.net/toplogin/scripts/ecpAgreementAlertHandle.js");
function IncludeCss(path) {
    var a = document.createElement('link');
    a.href = path;
    a.rel = 'stylesheet';
    var head = document.getElementsByTagName('head')[0];
    head.appendChild(a);
}
function AppendJs(jsurl, callback) {
	var oHead = document.getElementsByTagName('HEAD').item(0);
	var oScript = document.createElement("script");
	oScript.src = jsurl;
	if (callback) {
		oScript.onload = callback;
		oScript.onerror = callback;
	}
	document.head.appendChild(oScript);
}
if ((typeof Range !== "undefined") && !Range.prototype.createContextualFragment)
{
     Range.prototype.createContextualFragment = function(html)
     {
         var frag = document.createDocumentFragment(), 
         div = document.createElement("div");
         frag.appendChild(div);
         div.outerHTML = html;
         return frag;
     };
}
IncludeCss('https://login.cnki.net/toploginnew/content/ecp_agreement_base.css');
IncludeCss('https://login.cnki.net/toploginnew/content/ecp_agreement_style.css');
// IncludeCss('//e.dev.cnki.net/toplogin/content/ecp_agreement_base.css');
// IncludeCss('//e.dev.cnki.net/toplogin/content/ecp_agreement_style.css');
var agreementDomText = "<div id='ecp-agreement-wrap' style='display: none'> <div class='ecp-agreement-shadow'></div> <div class='ecp-agreement-continer'> <div class='ecp-agreement-top'> 提示 </div> <div class='ecp-agreement-text'> <p>请确认阅读并同意</p> <p><span>中国知网</span><a href='https://my.cnki.net/cnkiAgreement/cnkiUseAgreement.html' target='_blank'>使用协议</a>、<a href='https://my.cnki.net/cnkiAgreement/cnkiPrivacyAgreement.html' target='_blank'>隐私政策</a></p> </div> <div class='ecp-agreement-btn-group'> <span onclick='ecpAgreementCancel()'>取消</span> <span onclick='ecpAgreementConfirm()'>同意并登录</span> </div> </div> </div>"
var node = document.createRange().createContextualFragment(agreementDomText)
document.body.appendChild(node);

