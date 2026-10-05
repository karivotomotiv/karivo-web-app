import AmountList from "./AmountList";
export default function Giderler() {
  return (
    <AmountList
      title="Giderler"
      subtitle="Şirket gider kayıtlarını yönetin ve otomatik toplamı takip edin."
      endpoint="expenses"
      color="rose"
      testIdPrefix="expense"
    />
  );
}
