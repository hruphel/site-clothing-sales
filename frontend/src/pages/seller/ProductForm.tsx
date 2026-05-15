import { useMemo, useState } from "react";

import { ApiError } from "../../api";
import ErrorBox from "../../components/ErrorBox";

const STANDARD_SIZES = ["XS", "S", "M", "L", "XL", "XXL", "One Size"];

interface SizeRow {
  // Стабильный id для React-ключа (значение размера может меняться у custom-строк).
  rowId: string;
  size: string;
  quantity: string;
  custom: boolean;
}

interface Props {
  initial?: {
    name: string;
    price: string;
    stock: Record<string, number>;
    description: string;
    imageUrl: string | null;
  };
  submitLabel: string;
  onSubmit: (form: FormData) => Promise<void>;
  showRemoveImage?: boolean;
}

function buildInitialRows(stock: Record<string, number> | undefined): SizeRow[] {
  const rows: SizeRow[] = STANDARD_SIZES.map((s) => ({
    rowId: `std-${s}`,
    size: s,
    quantity: stock && stock[s] !== undefined ? String(stock[s]) : "",
    custom: false,
  }));
  if (stock) {
    let idx = 0;
    for (const [s, qty] of Object.entries(stock)) {
      if (!STANDARD_SIZES.includes(s)) {
        rows.push({
          rowId: `custom-init-${idx++}`,
          size: s,
          quantity: String(qty),
          custom: true,
        });
      }
    }
  }
  return rows;
}

export default function ProductForm({ initial, submitLabel, onSubmit, showRemoveImage }: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [price, setPrice] = useState(initial?.price ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [removeImage, setRemoveImage] = useState(false);
  const [rows, setRows] = useState<SizeRow[]>(() => buildInitialRows(initial?.stock));
  const [customNextId, setCustomNextId] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const activeCount = useMemo(
    () => rows.filter((r) => r.quantity.trim() !== "" && r.size.trim() !== "").length,
    [rows],
  );

  function setRowQuantity(rowId: string, value: string) {
    setRows((prev) => prev.map((r) => (r.rowId === rowId ? { ...r, quantity: value } : r)));
  }

  function toggleStandardRow(rowId: string, checked: boolean) {
    setRows((prev) =>
      prev.map((r) =>
        r.rowId === rowId ? { ...r, quantity: checked ? r.quantity || "1" : "" } : r,
      ),
    );
  }

  function setCustomSize(rowId: string, value: string) {
    setRows((prev) => prev.map((r) => (r.rowId === rowId ? { ...r, size: value } : r)));
  }

  function addCustomRow() {
    const id = `custom-${customNextId}`;
    setCustomNextId((n) => n + 1);
    setRows((prev) => [...prev, { rowId: id, size: "", quantity: "1", custom: true }]);
  }

  function removeRow(rowId: string) {
    setRows((prev) => prev.filter((r) => r.rowId !== rowId));
  }

  function buildStockJson(): { ok: true; value: string } | { ok: false; error: string } {
    const stock: Record<string, number> = {};
    const seen = new Set<string>();
    for (const row of rows) {
      const size = row.size.trim();
      const qtyRaw = row.quantity.trim();
      if (!size && !qtyRaw) continue;
      if (!size) {
        return { ok: false, error: "У одной из строк не указан размер." };
      }
      if (!qtyRaw) continue;
      const qty = Number(qtyRaw);
      if (!Number.isInteger(qty) || qty < 0 || qty > 9999) {
        return { ok: false, error: `Некорректное количество для размера «${size}».` };
      }
      const key = size.toUpperCase();
      if (seen.has(key)) {
        return { ok: false, error: `Размер «${size}» указан дважды.` };
      }
      seen.add(key);
      stock[size] = qty;
    }
    return { ok: true, value: JSON.stringify(stock) };
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const stockResult = buildStockJson();
      if (!stockResult.ok) {
        setError(stockResult.error);
        setSubmitting(false);
        return;
      }
      const form = new FormData(e.currentTarget);
      // Файл с пустым размером смущает FastAPI — удаляем.
      const file = form.get("image");
      if (file instanceof File && file.size === 0) {
        form.delete("image");
      }
      form.set("stock", stockResult.value);
      await onSubmit(form);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось сохранить.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit} encType="multipart/form-data">
      <ErrorBox message={error} />

      <label className="form-row">
        <span>Название</span>
        <input
          name="name"
          type="text"
          required
          maxLength={160}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>

      <label className="form-row">
        <span>Цена, ₽</span>
        <input
          name="price"
          type="text"
          required
          inputMode="decimal"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
        />
      </label>

      <div className="form-row">
        <span>Размеры и количество на складе</span>
        <p className="muted small" style={{ margin: "0 0 4px" }}>
          Поставьте галочку у нужного размера и укажите, сколько его в наличии. Размеры без галочки в каталог не попадут.
        </p>
        <div className="stock-editor">
          {rows.map((row) => {
            const checked = row.custom ? row.size.trim() !== "" : row.quantity.trim() !== "";
            return (
              <div className="stock-row" key={row.rowId}>
                {row.custom ? (
                  <>
                    <input
                      type="text"
                      className="stock-row__size"
                      value={row.size}
                      maxLength={8}
                      placeholder="Свой размер"
                      onChange={(e) => setCustomSize(row.rowId, e.target.value)}
                    />
                    <input
                      type="number"
                      className="stock-row__qty"
                      min={0}
                      max={9999}
                      value={row.quantity}
                      placeholder="кол-во"
                      onChange={(e) => setRowQuantity(row.rowId, e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn--ghost btn--small"
                      onClick={() => removeRow(row.rowId)}
                    >
                      Убрать
                    </button>
                  </>
                ) : (
                  <>
                    <label className="stock-row__check">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => toggleStandardRow(row.rowId, e.target.checked)}
                      />
                      <span>{row.size}</span>
                    </label>
                    <input
                      type="number"
                      className="stock-row__qty"
                      min={0}
                      max={9999}
                      value={row.quantity}
                      disabled={!checked}
                      placeholder="кол-во"
                      onChange={(e) => setRowQuantity(row.rowId, e.target.value)}
                    />
                    <span className="muted small">шт.</span>
                  </>
                )}
              </div>
            );
          })}
        </div>
        <div>
          <button type="button" className="btn btn--ghost btn--small" onClick={addCustomRow}>
            + Добавить свой размер
          </button>
        </div>
        <p className="muted small" style={{ margin: "4px 0 0" }}>
          Выбрано размеров: {activeCount}.
        </p>
      </div>

      <label className="form-row">
        <span>Описание</span>
        <textarea
          name="description"
          maxLength={4000}
          rows={5}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>

      <label className="form-row">
        <span>Фото (jpg, png, webp, gif — до 5 МБ)</span>
        <input name="image" type="file" accept="image/*" />
      </label>

      {showRemoveImage && initial?.imageUrl && (
        <label className="form-row form-row--inline">
          <input
            type="checkbox"
            name="remove_image"
            value="1"
            checked={removeImage}
            onChange={(e) => setRemoveImage(e.target.checked)}
          />
          <span>Удалить текущее фото</span>
        </label>
      )}

      {initial?.imageUrl && (
        <div className="muted small">
          Текущее фото:
          <br />
          <img
            src={initial.imageUrl}
            alt=""
            style={{ maxWidth: 200, marginTop: 8, borderRadius: 8 }}
          />
        </div>
      )}

      <div className="form-actions">
        <button className="btn btn--primary" type="submit" disabled={submitting}>
          {submitting ? "Сохраняем…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
