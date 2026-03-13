// 当隐私协议版本变更时  还在登录有效期内的用户不需要再次手动勾选隐私政策
var ecpAgreementVersions,ecpLoggedUserList;
var ecpUserLoggedFlag = false;
var ecpAgreementVersionsFlag = false;
try {
  currentAgreementVersions
} catch (error) {
  var currentAgreementVersions = "250615";
}
function ecpAgreementCancel() {
  document.getElementById('ecp-agreement-wrap').style.display = 'none';
}
function ecpAgreementConfirm() {
  ecpAgreementCancel();
  // 大陆注册页
  if(document.getElementById('protocolFlag')) {
    document.getElementById('protocolFlag').checked = true;
    // 调用父页面的登录事件
    parentLoginHandle();
    return
  }
  if(document.getElementById('agreementUnit')) {
    document.getElementById('agreementUnit').checked = true;
  }
  if(document.getElementById('agreementSms')) {
    document.getElementById('agreementSms').checked = true;
  }
  document.getElementById('agreement').checked = true;
  // 调用父页面的登录事件
  parentLoginHandle();
}
// 获取localStorage里的用户名和隐私政策版本号
function getAgreementVersions(userName) {
  ecpUserLoggedFlag = false;
  ecpAgreementVersionsFlag = false;
  ecpAgreementVersions = localStorage.getItem("ecpAgreementVersions");
  ecpLoggedUserList = localStorage.getItem("ecpLoggedUserList");
  if(ecpAgreementVersions === currentAgreementVersions) {
    ecpAgreementVersionsFlag = true;
  }
  if(ecpLoggedUserList) {
    var tempList = JSON.parse(ecpLoggedUserList);
    var tempList1 = [];
    for (var i = 0;i<tempList.length;i++) {
      if(tempList[i] != '' && tempList1.indexOf(tempList[i]) == -1) {
        tempList1.push(tempList[i]);
      }
    }
    for (var i = 0;i<tempList1.length;i++) {
      if((tempList1[i] === userName)) {
        ecpUserLoggedFlag = true;
        break;
      }
    }
    localStorage.setItem("ecpLoggedUserList",JSON.stringify(tempList1))
  }
  if (ecpAgreementVersionsFlag && ecpUserLoggedFlag) {
    $("#agreement").prop("checked",true);
    $("#agreementUnit").prop("checked",true);
  } 
  else {
    $("#agreement").prop("checked",false);
    $("#agreementUnit").prop("checked",false);
  }
}
// getAgreementVersions();