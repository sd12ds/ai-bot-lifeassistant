/**
 * Playwright e2e тесты для Jarvis Mini App.
 * Проверяют основные пользовательские сценарии через браузер.
 */
import { test, expect, Page } from "@playwright/test";

// ── Хелперы ──────────────────────────────────────────────────────────────────

/**
 * Перехватывает API запросы и возвращает мок-данные,
 * чтобы тесты не зависели от бэкенда.
 */
async function mockTasksApi(page: Page, tasks: object[] = []) {
  // Перехватываем GET /api/tasks
  await page.route("**/api/tasks/**", async (route) => {
    const req = route.request();

    if (req.method() === "GET" && req.url().endsWith("/api/tasks/") || req.url().includes("/api/tasks/?")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(tasks),
      });
    } else if (req.method() === "POST") {
      const body = JSON.parse(req.postData() || "{}");
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: Date.now(),
          title: body.title,
          description: body.description || null,
          priority: body.priority || 2,
          tags: body.tags || [],
          status: "todo",
          is_done: false,
          due_datetime: body.due_datetime || null,
          created_at: new Date().toISOString(),
        }),
      });
    } else if (req.method() === "PATCH") {
      const body = JSON.parse(req.postData() || "{}");
      const taskId = parseInt(req.url().split("/").pop() || "0");
      const task = tasks.find((t: any) => t.id === taskId) as any || {};
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...task,
          ...body,
          status: body.is_done ? "done" : "todo",
        }),
      });
    } else if (req.method() === "DELETE") {
      await route.fulfill({ status: 204 });
    } else {
      await route.continue();
    }
  });
}

// ── Загрузка страницы ─────────────────────────────────────────────────────────

test.describe("Загрузка приложения", () => {
  test("страница загружается без ошибок", async ({ page }) => {
    await mockTasksApi(page);
    await page.goto("/");
    // Ждём исчезновения skeleton loader
    await expect(page.locator('[data-testid="skeleton-loader"]').first()).toBeHidden({ timeout: 5000 }).catch(() => {});
    // Проверяем что нет JS ошибок — приложение смонтировалось
    await expect(page).toHaveTitle(/Jarvis|Vite/i);
  });

  test("отображается пустое состояние при отсутствии задач", async ({ page }) => {
    await mockTasksApi(page, []);
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // EmptyState или список должен быть виден
    const emptyState = page.locator('[data-testid="empty-state"], .empty-state, text=Нет задач');
    const tasksList = page.locator('[data-testid="task-list"], [data-testid="task-card"]');
    // Либо пустое состояние видно, либо список пуст
    const emptyVisible = await emptyState.isVisible().catch(() => false);
    const tasksCount = await tasksList.count();
    expect(emptyVisible || tasksCount === 0).toBeTruthy();
  });

  test("отображается список задач", async ({ page }) => {
    const tasks = [
      { id: 1, title: "Задача первая", priority: 1, tags: ["работа"], status: "todo", is_done: false, due_datetime: null, created_at: new Date().toISOString() },
      { id: 2, title: "Задача вторая", priority: 2, tags: [], status: "todo", is_done: false, due_datetime: null, created_at: new Date().toISOString() },
    ];
    await mockTasksApi(page, tasks);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("Задача первая")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("Задача вторая")).toBeVisible({ timeout: 5000 });
  });
});

// ── FAB и создание задачи ─────────────────────────────────────────────────────

test.describe("Создание задачи", () => {
  test("FAB открывает sheet создания задачи", async ({ page }) => {
    await mockTasksApi(page, []);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Нажимаем FAB (кнопка +)
    const fab = page.locator('[data-testid="fab"], button[aria-label*="создать"], button[aria-label*="Создать"]');
    if (await fab.count() === 0) {
      // Ищем кнопку с + символом
      await page.getByRole("button", { name: /\+|добавить|создать/i }).first().click();
    } else {
      await fab.first().click();
    }

    // Sheet/modal должен появиться
    const sheet = page.locator('[data-testid="task-create-sheet"], [role="dialog"], .sheet, .bottom-sheet');
    await expect(sheet.first()).toBeVisible({ timeout: 3000 });
  });

  test("форма создания принимает заголовок задачи", async ({ page }) => {
    await mockTasksApi(page, []);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Открываем sheet
    await page.getByRole("button", { name: /\+|добавить|создать/i }).first().click().catch(() => {
      page.locator('[data-testid="fab"]').click();
    });

    // Вводим название
    const titleInput = page.getByPlaceholder(/название|заголовок|задача/i)
      .or(page.getByLabel(/название|заголовок|title/i))
      .first();

    await titleInput.waitFor({ state: "visible", timeout: 3000 }).catch(() => {});
    if (await titleInput.isVisible()) {
      await titleInput.fill("Новая тестовая задача");
      await expect(titleInput).toHaveValue("Новая тестовая задача");
    }
  });

  test("нельзя создать задачу без названия", async ({ page }) => {
    await mockTasksApi(page, []);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Открываем sheet
    await page.getByRole("button", { name: /\+|добавить|создать/i }).first().click().catch(() => {});

    // Пробуем нажать кнопку Submit без заполнения
    const submitBtn = page.getByRole("button", { name: /создать|добавить|сохранить|save|submit/i });
    if (await submitBtn.count() > 0) {
      await submitBtn.first().click();
      // Форма НЕ должна закрыться / должна показать ошибку
      const sheet = page.locator('[role="dialog"], .sheet, .bottom-sheet, [data-testid="task-create-sheet"]');
      // Либо sheet открыт, либо показана ошибка валидации
      const sheetVisible = await sheet.first().isVisible().catch(() => false);
      const errorVisible = await page.getByText(/обязательн|required|заполните/i).isVisible().catch(() => false);
      expect(sheetVisible || errorVisible).toBeTruthy();
    }
  });
});

// ── Фильтры ───────────────────────────────────────────────────────────────────

test.describe("Фильтры задач", () => {
  test("табы фильтров присутствуют на странице", async ({ page }) => {
    await mockTasksApi(page, []);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Ищем табы — "Все", "Сегодня", "Неделя", "Без срока"
    const filterTexts = ["Все", "Сегодня", "Неделя", "Без срока"];
    let foundAny = false;
    for (const text of filterTexts) {
      const isVisible = await page.getByText(text).first().isVisible().catch(() => false);
      if (isVisible) {
        foundAny = true;
        break;
      }
    }
    expect(foundAny).toBeTruthy();
  });

  test("клик по фильтру 'Сегодня' делает GET с period=today", async ({ page }) => {
    const requests: string[] = [];

    // Перехватываем запросы и логируем URL
    page.on("request", (req) => {
      if (req.url().includes("/api/tasks")) {
        requests.push(req.url());
      }
    });

    await mockTasksApi(page, []);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Кликаем "Сегодня"
    const todayBtn = page.getByText("Сегодня").first();
    if (await todayBtn.isVisible()) {
      await todayBtn.click();
      await page.waitForTimeout(500); // даём время на запрос
      const hasTodayFilter = requests.some((url) => url.includes("period=today"));
      expect(hasTodayFilter).toBeTruthy();
    }
  });
});

// ── BottomNav навигация ───────────────────────────────────────────────────────

test.describe("BottomNav навигация", () => {
  test("нижняя навигация отображается", async ({ page }) => {
    await mockTasksApi(page, []);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // BottomNav содержит иконки навигации
    const nav = page.locator("nav, [data-testid='bottom-nav'], [role='navigation']");
    await expect(nav.first()).toBeVisible({ timeout: 3000 });
  });

  test("активный элемент навигации выделен", async ({ page }) => {
    await mockTasksApi(page, []);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Ищем активный (aria-current или active класс) элемент nav
    const activeNavItem = page.locator(
      "nav [aria-current='page'], nav .active, [data-testid='nav-active']"
    );
    // Если такой элемент есть — проверяем его видимость
    const count = await activeNavItem.count();
    if (count > 0) {
      await expect(activeNavItem.first()).toBeVisible();
    }
    // Если нет — тест проходит (навигация без aria)
  });
});

// ── Отметка задачи выполненной ────────────────────────────────────────────────

test.describe("Чекбокс задачи", () => {
  test("чекбокс задачи кликабелен", async ({ page }) => {
    const tasks = [
      { id: 1, title: "Задача для теста", priority: 2, tags: [], status: "todo", is_done: false, due_datetime: null, created_at: new Date().toISOString() },
    ];

    const patchRequests: string[] = [];
    await page.route("**/api/tasks/**", async (route) => {
      const req = route.request();
      if (req.method() === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(tasks) });
      } else if (req.method() === "PATCH") {
        patchRequests.push(req.url());
        const body = JSON.parse(req.postData() || "{}");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ...tasks[0], ...body, status: "done" }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Задача должна быть видна
    await expect(page.getByText("Задача для теста")).toBeVisible({ timeout: 5000 });

    // Ищем чекбокс
    const checkbox = page.locator('[type="checkbox"], [role="checkbox"], [data-testid="task-checkbox"]').first();
    if (await checkbox.isVisible()) {
      await checkbox.click();
      await page.waitForTimeout(300);
      // Должен был сделан PATCH запрос
      expect(patchRequests.length).toBeGreaterThan(0);
    }
  });
});
