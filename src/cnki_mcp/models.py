"""数据模型定义"""

from pydantic import BaseModel, Field
from enum import Enum


class SearchType(str, Enum):
    SU = "SU"
    TI = "TI"
    AU = "AU"
    KY = "KY"
    AB = "AB"
    FT = "FT"

SEARCH_TYPE_NAMES = {
    SearchType.SU: "主题",
    SearchType.TI: "篇名",
    SearchType.AU: "作者",
    SearchType.KY: "关键词",
    SearchType.AB: "摘要",
    SearchType.FT: "全文",
}


class CNKIQueryRequest(BaseModel):
    keyword: str = Field(..., description="检索关键词")
    search_type: SearchType = Field(default=SearchType.SU, description="检索类型: SU=主题, TI=篇名, AU=作者, KY=关键词, AB=摘要, FT=全文")
    db_code: str = Field(default="CJFD", description="数据库代码: CJFD=期刊, CDMD=硕博, CMFD=会议")
    page_size: int = Field(default=10, ge=1, le=50, description="每页条数")
    page_num: int = Field(default=1, ge=1, description="页码")
    filter_resource: str = Field(default="", description="筛选资源类型: DISSERTATION=学位论文, JOURNAL=期刊, CONFERENCE=会议, NEWSPAPER=报纸等")


class CNKIPaper(BaseModel):
    title: str = Field(default="", description="论文标题")
    author: str = Field(default="", description="作者")
    author_affiliation: str = Field(default="", description="作者单位")
    source: str = Field(default="", description="来源期刊")
    publish_time: str = Field(default="", description="发表时间")
    abstract: str = Field(default="", description="摘要")
    keywords: str = Field(default="", description="关键词")
    doi: str = Field(default="", description="DOI")
    fund: str = Field(default="", description="基金资助")
    album: str = Field(default="", description="专辑")
    topic: str = Field(default="", description="专题")
    classification: str = Field(default="", description="分类号")
    online_publish_time: str = Field(default="", description="在线发表时间")
    citation_gbt: str = Field(default="", description="GB/T 7714-2015格式引用")
    citation_cnki: str = Field(default="", description="知网研学格式引用")
    citation_endnote: str = Field(default="", description="EndNote格式引用")
    link: str = Field(default="", description="链接")


class CNKIQueryResult(BaseModel):
    total: int = Field(default=0, description="结果总数")
    page_num: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=10, description="每页条数")
    results: list[CNKIPaper] = Field(default_factory=list, description="论文列表")
