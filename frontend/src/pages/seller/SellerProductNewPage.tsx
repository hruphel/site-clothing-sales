import { useNavigate } from "react-router-dom";

import { api } from "../../api";
import ProductForm from "./ProductForm";

export default function SellerProductNewPage() {
  const navigate = useNavigate();

  return (
    <section className="section">
      <div className="container narrow">
        <div className="section-header">
          <span className="eyebrow">Новая заявка</span>
          <h2>Новая заявка на товар</h2>
        </div>
        <ProductForm
          submitLabel="Отправить на модерацию"
          onSubmit={async (form) => {
            await api.postForm("/api/seller/products", form);
            navigate("/seller/products");
          }}
        />
      </div>
    </section>
  );
}
