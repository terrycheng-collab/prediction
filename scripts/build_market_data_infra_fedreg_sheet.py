"""
Builds an Excel sheet of Federal Register publications related to the SEC's
"Market Data Infrastructure" rule (File No. S7-03-20 / RIN 3235-AM61), plus
the surrounding policy lineage cited in Budish, Lee & Shim (2024, JPE) --
"A Theory of Stock Exchange Competition and Innovation: Will the Market Fix
the Market?" (ExchangeComp_pub.pdf).

All metadata pulled from the Federal Register API (federalregister.gov/api/v1)
on 2026-07-31 and cross-checked against sec.gov release pages. Column schema
mirrors the fed_reg project's "00_master list of FR.xlsx" (docid, date_published,
doctype, title, action, citation_short, frdoc, rin, rins_all, link_html), with
group/release_no/file_no/note columns added for this smaller, curated set.
"""
import pandas as pd

ROWS = [
    # --- Group 1: Market Data Infrastructure rulemaking (S7-03-20 / RIN 3235-AM61) ---
    dict(
        group="1. MDI rulemaking",
        frdoc="2020-03760",
        date_published="2020-03-24",
        doctype="Proposed Rule",
        title="Market Data Infrastructure",
        action="Proposed rule.",
        citation_short="85 FR 16726",
        release_no="34-88216",
        file_no="S7-03-20",
        rin="3235-AM61",
        link_html="https://www.federalregister.gov/documents/2020/03/24/2020-03760/market-data-infrastructure",
        note="Proposing release. Cites the paper's finding of exchange market power over proprietary data/speed technology and its revenue estimates (per paper's own account of its influence).",
    ),
    dict(
        group="1. MDI rulemaking",
        frdoc="2020-28370",
        date_published="2021-04-09",
        doctype="Rule",
        title="Market Data Infrastructure",
        action="Final rule.",
        citation_short="86 FR 18596",
        release_no="34-90610",
        file_no="S7-03-20",
        rin="3235-AM61",
        link_html="https://www.federalregister.gov/documents/2021/04/09/2020-28370/market-data-infrastructure",
        note="Adopted unanimously Dec 2020; published in FR Apr 2021. Challenged by NYSE/Nasdaq/Cboe; upheld by D.C. Circuit May 2022 (not itself an FR document).",
    ),
    dict(
        group="1. MDI rulemaking",
        frdoc="2021-11282",
        date_published="2021-06-01",
        doctype="Rule",
        title="Market Data Infrastructure",
        action="Final rule; correction.",
        citation_short="86 FR 29195",
        release_no="34-90610A",
        file_no="S7-03-20",
        rin="3235-AM61",
        link_html="https://www.federalregister.gov/documents/2021/06/01/2021-11282/market-data-infrastructure",
        note="Technical correction to the final rule.",
    ),
    dict(
        group="1. MDI rulemaking",
        frdoc="2024-02951",
        date_published="2024-02-13",
        doctype="Notice",
        title="Proposed Collection; Comment Request; Extension: Market Data Infrastructure",
        action=None,
        citation_short="89 FR 10115",
        release_no=None,
        file_no="SEC File No. 270-823",
        rin=None,
        link_html="https://www.federalregister.gov/documents/2024/02/13/2024-02951/proposed-collection-comment-request-extension-market-data-infrastructure",
        note="Paperwork Reduction Act renewal of the rule's information-collection burden estimate (OMB Control No. 3235-0778). Shows the rule is still an active, maintained collection as of 2024.",
    ),
    # --- Group 2: Companion NMS Plan directive/approval implementing MDI (File No. 4-757) ---
    dict(
        group="2. NMS Plan implementation",
        frdoc="2020-10041",
        date_published="2020-05-13",
        doctype="Notice",
        title="Order Directing the Exchanges and the Financial Industry Regulatory Authority To Submit a New National Market System Plan Regarding Consolidated Equity Market Data",
        action=None,
        citation_short="85 FR 28702",
        release_no="34-88827",
        file_no="4-757",
        rin=None,
        link_html="https://www.federalregister.gov/documents/2020/05/13/2020-10041/order-directing-the-exchanges-and-the-financial-industry-regulatory-authority-to-submit-a-new",
        note="SEC-directed the exchanges/FINRA to build the 'competing consolidator' NMS Plan required to operationalize the proposed MDI rule -- issued while the rule was still only proposed.",
    ),
    dict(
        group="2. NMS Plan implementation",
        frdoc="2021-17113",
        date_published="2021-08-11",
        doctype="Notice",
        title="Joint Industry Plan; Order Approving, as Modified, a National Market System Plan Regarding Consolidated Equity Market Data",
        action=None,
        citation_short="86 FR 44142",
        release_no="34-92586",
        file_no="4-757",
        rin=None,
        link_html="https://www.federalregister.gov/documents/2021/08/11/2021-17113/joint-industry-plan-order-approving-as-modified-a-national-market-system-plan-regarding",
        note="SEC approval of the industry-submitted plan -- the actual operational implementation step for the 'competing consolidator' model.",
    ),
    # --- Group 3: The precursor invitation the paper credits with opening the door ---
    dict(
        group="3. Thinly-traded securities statement",
        frdoc="2019-22994",
        date_published="2019-10-24",
        doctype="Proposed Rule",
        title="Commission Statement on Market Structure Innovation for Thinly Traded Securities",
        action="Commission statement.",
        citation_short="84 FR 56956",
        release_no="34-87327",
        file_no="S7-18-19",
        rin=None,
        link_html="https://www.federalregister.gov/documents/2019/10/24/2019-22994/commission-statement-on-market-structure-innovation-for-thinly-traded-securities",
        note="Invited exchanges to propose batch auctions and offered UTP-suspension exclusivity for innovators -- directly mirrors the paper's 'push' policy proposal. The paper's Sec. V cites this as evidence of its influence.",
    ),
    # --- Group 4: Cboe BYX Periodic Auctions -- the concrete auction-design response ---
    dict(
        group="4. Cboe BYX Periodic Auctions (SR-CboeBYX-2020-021)",
        frdoc="2020-16876",
        date_published="2020-08-04",
        doctype="Notice",
        title="Self-Regulatory Organizations; Cboe BYX Exchange, Inc.; Notice of Filing of a Proposed Rule Change To Introduce Periodic Auctions for the Trading of U.S. Equity Securities",
        action=None,
        citation_short="85 FR 47262",
        release_no="34-89424",
        file_no="SR-CboeBYX-2020-021",
        rin=None,
        link_html="https://www.federalregister.gov/documents/2020/08/04/2020-16876/self-regulatory-organizations-cboe-byx-exchange-inc-notice-of-filing-of-a-proposed-rule-change-to",
        note="Original filing: an auction-based design targeted at thinly-traded names, filed under the SEC's 2019 program.",
    ),
    dict(
        group="4. Cboe BYX Periodic Auctions (SR-CboeBYX-2020-021)",
        frdoc="2020-20360",
        date_published="2020-09-16",
        doctype="Notice",
        title="Self-Regulatory Organizations; Cboe BYX Exchange, Inc.; Notice of Designation of a Longer Period for Commission Action on a Proposed Rule Change To Introduce Periodic Auctions for the Trading of U.S. Equity Securities",
        action=None,
        citation_short="85 FR 57891",
        release_no="34-89820",
        file_no="SR-CboeBYX-2020-021",
        rin=None,
        link_html="https://www.federalregister.gov/documents/2020/09/16/2020-20360/self-regulatory-organizations-cboe-byx-exchange-inc-notice-of-designation-of-a-longer-period-for",
        note="Procedural extension of SEC review period.",
    ),
    dict(
        group="4. Cboe BYX Periodic Auctions (SR-CboeBYX-2020-021)",
        frdoc="2020-24495",
        date_published="2020-11-05",
        doctype="Notice",
        title="Self-Regulatory Organizations; Cboe BYX Exchange, Inc.; Notice of Filing of Amendment No. 2 and Order Instituting Proceedings To Determine Whether To Approve or Disapprove a Proposed Rule Change, as Modified by Amendment No. 2, To Introduce Periodic Auctions for the Trading of U.S. Equity Securities",
        action=None,
        citation_short="85 FR 70678",
        release_no="34-90288",
        file_no="SR-CboeBYX-2020-021",
        rin=None,
        link_html="https://www.federalregister.gov/documents/2020/11/05/2020-24495/self-regulatory-organizations-cboe-byx-exchange-inc-notice-of-filing-of-amendment-no-2-and-order",
        note="SEC instituted formal proceedings (a heavier-scrutiny track) on the amended proposal.",
    ),
    dict(
        group="4. Cboe BYX Periodic Auctions (SR-CboeBYX-2020-021)",
        frdoc="2021-02006",
        date_published="2021-02-01",
        doctype="Notice",
        title="Self-Regulatory Organizations; Cboe BYX Exchange, Inc.; Notice of Designation of a Longer Period for Commission Action on Proceedings To Determine Whether To Approve or Disapprove a Proposed Rule Change, as Modified by Amendment No. 2, To Introduce Periodic Auctions for the Trading of U.S. Equity Securities",
        action=None,
        citation_short="86 FR 7753",
        release_no="34-90993",
        file_no="SR-CboeBYX-2020-021",
        rin=None,
        link_html="https://www.federalregister.gov/documents/2021/02/01/2021-02006/self-regulatory-organizations-cboe-byx-exchange-inc-notice-of-designation-of-a-longer-period-for",
        note="Further procedural extension.",
    ),
    dict(
        group="4. Cboe BYX Periodic Auctions (SR-CboeBYX-2020-021)",
        frdoc="2021-06676",
        date_published="2021-04-01",
        doctype="Notice",
        title="Self-Regulatory Organizations; Cboe BYX Exchange, Inc.; Notice of Filing of Amendments No. 3 and No. 4, and Order Granting Accelerated Approval of a Proposed Rule Change, as Modified by Amendments No. 3 and No. 4, To Introduce Periodic Auctions for the Trading of U.S. Equity Securities",
        action=None,
        citation_short="86 FR 17230",
        release_no="34-91423",
        file_no="SR-CboeBYX-2020-021",
        rin=None,
        link_html="https://www.federalregister.gov/documents/2021/04/01/2021-06676/self-regulatory-organizations-cboe-byx-exchange-inc-notice-of-filing-of-amendments-no-3-and-no-4-and",
        note="APPROVED (accelerated approval). The one concrete instance of an auction-style mechanism reaching live SEC approval in this whole thread -- notably an add-on periodic-auction feature, not a wholesale switch to continuous-time frequent batch auctions.",
    ),
    # --- Group 5: The broader post-paper auction-based push, and its 2025 reversal ---
    dict(
        group="5. Order Competition Rule (S7-31-22)",
        frdoc="2022-27617",
        date_published="2023-01-03",
        doctype="Proposed Rule",
        title="Order Competition Rule",
        action="Proposed rule.",
        citation_short="88 FR 128",
        release_no="34-96495",
        file_no="S7-31-22",
        rin="3235-AM57",
        link_html="https://www.federalregister.gov/documents/2023/01/03/2022-27617/order-competition-rule",
        note="Would have forced most retail marketable orders through open, auction-based competition before internalization -- the closest post-paper analogue to a 'Discrete'-style mandate, though not citing this paper directly.",
    ),
    dict(
        group="5. Order Competition Rule (S7-31-22)",
        frdoc="2025-11110",
        date_published="2025-06-17",
        doctype="Proposed Rule",
        title="Withdrawal of Proposed Regulatory Actions",
        action="Notice of withdrawal of proposed rules.",
        citation_short="90 FR 25531",
        release_no="33-11377, 34-103247, IA-6885, IC-35635",
        file_no="S7-31-22 (one of 18 withdrawn dockets)",
        rin=None,
        link_html="https://www.federalregister.gov/documents/2025/06/17/2025-11110/withdrawal-of-proposed-regulatory-actions",
        note="Formally withdrew the Order Competition Rule (and 13 other Gensler-era proposals) effective 2025-06-17. A reversal, not further progress, on the auction-based-order-competition front.",
    ),
]

df = pd.DataFrame(ROWS)
df.insert(0, "docid", range(1, len(df) + 1))
df["date_published"] = pd.to_datetime(df["date_published"])

col_order = [
    "docid", "group", "date_published", "doctype", "title", "action",
    "citation_short", "release_no", "file_no", "rin", "frdoc", "link_html", "note",
]
df = df[col_order]

out_path = "/home/terryc/projects/prediction/exports/market_data_infrastructure_fedreg.xlsx"
with pd.ExcelWriter(out_path, engine="openpyxl", datetime_format="yyyy-mm-dd") as writer:
    df.to_excel(writer, sheet_name="FR documents", index=False)

    readme = pd.DataFrame({
        "": [
            "Federal Register publications related to the SEC's 'Market Data Infrastructure' rule "
            "(File No. S7-03-20) and its policy lineage, as discussed in Budish, Lee & Shim (2024, JPE), "
            "'A Theory of Stock Exchange Competition and Innovation: Will the Market Fix the Market?' "
            "(see ExchangeComp_pub.pdf in this project).",
            "",
            "All rows sourced from the Federal Register API (federalregister.gov/api/v1/documents), "
            "retrieved 2026-07-31, and cross-checked against sec.gov release pages where noted.",
            "",
            "Groups:",
            "1. MDI rulemaking          -- the proposed/final rule itself and its PRA maintenance",
            "2. NMS Plan implementation -- the companion order directing/approving the 'competing consolidator' plan",
            "3. Thinly-traded securities statement -- the 2019 precursor that invited batch-auction proposals",
            "4. Cboe BYX Periodic Auctions -- the one concrete auction-design proposal filed under that invitation, "
            "   through to its approval",
            "5. Order Competition Rule -- the broader 2022 auction-based retail-order push and its 2025 withdrawal",
            "",
            "Column schema follows projects/fed_reg/00_master list of FR.xlsx (docid, date_published, doctype, "
            "title, action, citation_short, frdoc, rin, link_html), with group/release_no/file_no/note added "
            "for this smaller curated set.",
            "",
            "Not included: the D.C. Circuit litigation upholding the final rule (May 2022) and SEC Commissioner "
            "statements/speeches (e.g. Robert Jackson's Jan 2020 remarks) -- neither is a Federal Register "
            "publication.",
        ]
    })
    readme.to_excel(writer, sheet_name="README", index=False, header=False)

    ws = writer.sheets["FR documents"]
    widths = {"A": 7, "B": 30, "C": 14, "D": 12, "E": 60, "F": 22, "G": 14,
              "H": 40, "I": 26, "J": 12, "K": 12, "L": 60, "M": 70}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"

    ws2 = writer.sheets["README"]
    ws2.column_dimensions["A"].width = 110

print(f"Wrote {len(df)} rows to {out_path}")
