import AmountList from "./AmountList";
export default function Gelirler() {
  return (
    <AmountList
      title="Gelirler"
      subtitle="Şirket gelir kayıtlarını ekleyin, düzenleyin ve toplamı anında görün."
      endpoint="incomes"
      color="emerald"
      testIdPrefix="income"
    />
  );
}
