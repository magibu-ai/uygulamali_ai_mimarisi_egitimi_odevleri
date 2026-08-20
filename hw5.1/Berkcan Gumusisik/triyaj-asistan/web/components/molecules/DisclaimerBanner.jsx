// Molekül: yasal/etik uyarı bandı — asistan tanı koymaz.
export default function DisclaimerBanner() {
  return (
    <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
      <span className="text-base leading-none">⚠️</span>
      <p>
        Bu asistan <b>tanı koymaz</b>, yalnızca yönlendirir. Acil bir durumda
        vakit kaybetmeden <b>112</b>&apos;yi arayın.
      </p>
    </div>
  );
}
